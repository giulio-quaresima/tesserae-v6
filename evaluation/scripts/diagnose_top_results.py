#!/usr/bin/env python3
"""
Diagnostic: dump top fusion results with detailed IDF / rarity information.

Runs a single text pair through the fusion pipeline and outputs a detailed
report of the top N results, showing:
  - All matched words with their corpus IDF (raw and headword-normalized)
  - Geometric mean IDF, rarity multiplier, zone classification
  - Min-IDF gate status (triggered or not)
  - Flags any result where a matched word has idf < 1.0

Usage:
    TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/diagnose_top_results.py

Override defaults with environment variables:
    SOURCE_FILE=vergil.aeneid.part.7.tess
    TARGET_FILE=silius_italicus.punica.part.2.tess
    TOP_N=200
"""

import json
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.fusion import (
    CHANNEL_WEIGHTS, CHANNEL_CONFIGS, CHANNEL_ORDER,
    CONVERGENCE_BONUS, CONVERGENCE_IDF_POWER,
    RARITY_IDF_FLOOR, RARITY_IDF_THRESHOLD,
    RARITY_MIN_IDF_THRESHOLD, RARITY_MIN_IDF_PENALTY,
    RARITY_PENALTY_POWER, RARITY_BOOST_WEIGHT, RARITY_BOOST_CAP,
    RARITY_NEAR_STOPWORD_CUTOFF, RARITY_RAMP_OFFSET,
    SINGLE_WORD_PENALTY, NO_SIGNIFICANT_WORDS_PENALTY,
    run_fusion_search,
    _get_corpus_doc_freqs, _get_total_texts, _get_headword_map,
)

TEXTS_DIR = PROJECT_ROOT / "texts"

# Defaults — override with env vars
SOURCE_FILE = os.environ.get("SOURCE_FILE", "vergil.aeneid.part.7.tess")
TARGET_FILE = os.environ.get("TARGET_FILE", "silius_italicus.punica.part.2.tess")
TOP_N = int(os.environ.get("TOP_N", "200"))


def find_text_path(filename):
    """Find a .tess file under texts/."""
    for p in TEXTS_DIR.rglob(filename):
        return p
    return None


def compute_rarity_details(result, doc_freq_map, headword_map, total_texts):
    """Compute detailed rarity info for a single result, matching fuse_results logic."""
    log_total = math.log(total_texts)
    mw_list = result.get("matched_words", [])

    # Collect per-word IDF details
    word_details = []
    word_pair_best = {}  # (src_word, tgt_word) -> (corpus_idf, df, lemma)

    for mw in mw_list:
        lemma = mw.get("lemma", "")
        if not lemma or lemma.startswith('['):
            continue
        df = doc_freq_map.get(lemma, 0)
        if df <= 0:
            continue

        # Headword info
        hw = headword_map.get(lemma)
        hw_df = doc_freq_map.get(hw, 0) if hw and hw != lemma else 0

        cidf = log_total - math.log(df)

        # What the IDF would be WITHOUT headword normalization
        # (use raw index df for this lemma form)
        raw_df_for_lemma = df
        # If headword normalization bumped this up, the "raw" df is the
        # original index df for this form. We need to check what
        # get_document_frequencies_batch would have returned.
        # Since _get_corpus_doc_freqs already applied normalization,
        # we can't easily separate. But we can compute: if hw_df > raw_index_df,
        # then df was normalized. We report both.

        word_details.append({
            "lemma": lemma,
            "source_word": mw.get("source_word", ""),
            "target_word": mw.get("target_word", ""),
            "df": df,
            "idf": cidf,
            "headword": hw if hw and hw != lemma else None,
            "headword_df": hw_df if hw and hw != lemma else None,
        })

        sw = mw.get('source_word', '')
        tw = mw.get('target_word', '')
        word_key = (sw, tw) if (sw or tw) else (lemma,)
        existing = word_pair_best.get(word_key)
        if existing is None or df > existing[1]:
            word_pair_best[word_key] = (cidf, df, lemma)

    corpus_idfs = [cidf for cidf, _, _ in word_pair_best.values()]
    n_unique_words = len(corpus_idfs)
    n_significant_words = sum(1 for cidf in corpus_idfs
                              if cidf >= RARITY_IDF_THRESHOLD)

    # Compute geometric mean IDF
    if corpus_idfs:
        log_sum = sum(math.log(max(idf, 0.001)) for idf in corpus_idfs)
        geom_mean_idf = math.exp(log_sum / len(corpus_idfs))
    else:
        geom_mean_idf = 1.0

    # Compute multiplier (same logic as fuse_results)
    cutoff = RARITY_NEAR_STOPWORD_CUTOFF
    idf_floor = RARITY_IDF_FLOOR
    idf_threshold = RARITY_IDF_THRESHOLD
    ramp_offset = RARITY_RAMP_OFFSET
    ramp_start = idf_floor + ramp_offset
    ramp_range = 1.0 - ramp_start
    thresh_range = idf_threshold - cutoff

    if not corpus_idfs:
        multiplier = 1.0
        zone = "no_data"
    elif geom_mean_idf < cutoff:
        multiplier = idf_floor
        zone = "zone1_floor"
    elif geom_mean_idf < idf_threshold:
        t = (geom_mean_idf - cutoff) / thresh_range
        multiplier = ramp_start + t * ramp_range
        zone = "zone2_ramp"
    else:
        n_ch = len(result.get("channels", []))
        channel_factor = min(1.0, (n_ch - 1) / 5.0)
        word_factor = min(1.0, (n_unique_words - 1) / 3.0)
        boost_factor = min(channel_factor, word_factor)
        multiplier = min(RARITY_BOOST_CAP,
                         1.0 + RARITY_BOOST_WEIGHT * boost_factor *
                         math.log(geom_mean_idf / idf_threshold))
        zone = "zone3_boost"

    # Single-word penalty / no-significant-words penalty
    single_word_penalty_applied = False
    no_sig_penalty_applied = False
    if corpus_idfs:
        if n_unique_words <= 1:
            multiplier *= SINGLE_WORD_PENALTY
            single_word_penalty_applied = True
        elif n_significant_words == 0:
            multiplier *= NO_SIGNIFICANT_WORDS_PENALTY
            no_sig_penalty_applied = True

    # Min-IDF gate
    min_idf_gate_triggered = False
    min_word_idf = min(corpus_idfs) if corpus_idfs else 99.0
    if RARITY_MIN_IDF_PENALTY < 1.0 and RARITY_MIN_IDF_THRESHOLD > 0:
        if corpus_idfs and min(corpus_idfs) < RARITY_MIN_IDF_THRESHOLD:
            multiplier *= RARITY_MIN_IDF_PENALTY
            min_idf_gate_triggered = True

    # Flag low-IDF words
    has_low_idf = any(d["idf"] < 1.0 for d in word_details)

    return {
        "word_details": word_details,
        "geom_mean_idf": geom_mean_idf,
        "min_word_idf": min_word_idf,
        "multiplier": multiplier,
        "effective_mult_squared": multiplier ** RARITY_PENALTY_POWER,
        "zone": zone,
        "n_unique_words": n_unique_words,
        "n_significant_words": n_significant_words,
        "n_channels": len(result.get("channels", [])),
        "single_word_penalty": single_word_penalty_applied,
        "no_sig_penalty": no_sig_penalty_applied,
        "min_idf_gate": min_idf_gate_triggered,
        "has_low_idf": has_low_idf,
    }


def main():
    print("=" * 80)
    print("FUSION DIAGNOSTIC: Top Results IDF Analysis")
    print("=" * 80)
    print(f"Source: {SOURCE_FILE}")
    print(f"Target: {TARGET_FILE}")
    print(f"Top N:  {TOP_N}")
    print()

    # Print current config
    print("--- Current Config ---")
    print(f"RARITY_MIN_IDF_THRESHOLD = {RARITY_MIN_IDF_THRESHOLD}")
    print(f"RARITY_MIN_IDF_PENALTY   = {RARITY_MIN_IDF_PENALTY}")
    print(f"SINGLE_WORD_PENALTY      = {SINGLE_WORD_PENALTY}")
    print(f"RARITY_IDF_FLOOR         = {RARITY_IDF_FLOOR}")
    print(f"RARITY_IDF_THRESHOLD     = {RARITY_IDF_THRESHOLD}")
    print(f"Channel weights: {CHANNEL_WEIGHTS}")
    print()

    # Find text files
    source_path = find_text_path(SOURCE_FILE)
    target_path = find_text_path(TARGET_FILE)
    if not source_path or not target_path:
        print(f"ERROR: Could not find text files")
        print(f"  Source: {source_path}")
        print(f"  Target: {target_path}")
        sys.exit(1)

    # Initialize
    print("Initializing components...")
    tp = TextProcessor()
    matcher = Matcher()
    scorer = Scorer()

    # Process texts
    print(f"Processing {SOURCE_FILE}...")
    source_units = tp.process_file(str(source_path), "la", "line")
    print(f"  -> {len(source_units)} lines")

    print(f"Processing {TARGET_FILE}...")
    target_units = tp.process_file(str(target_path), "la", "line")
    print(f"  -> {len(target_units)} lines")

    # Run fusion search
    print(f"\nRunning fusion search...")
    t0 = time.time()
    results = run_fusion_search(
        source_units, target_units, matcher, scorer,
        SOURCE_FILE, TARGET_FILE,
        language='la', mode='merged', max_results=5000,
        source_path=str(source_path), target_path=str(target_path),
    )
    elapsed = time.time() - t0
    print(f"  -> {len(results)} results in {elapsed:.1f}s")

    # Pre-fetch headword map and corpus doc freqs for all matched words
    print("\nPre-fetching IDF data for diagnosis...")
    all_lemmas = set()
    for r in results[:TOP_N]:
        for mw in r.get("matched_words", []):
            lemma = mw.get("lemma", "")
            if lemma and not lemma.startswith('['):
                all_lemmas.add(lemma)

    total_texts = _get_total_texts('la')
    doc_freq_map = _get_corpus_doc_freqs(list(all_lemmas), 'la')
    headword_map = _get_headword_map('la')
    print(f"  -> {len(all_lemmas)} unique lemmas, total_texts={total_texts}")

    # Analyze top results
    print(f"\n{'=' * 80}")
    print(f"TOP {TOP_N} RESULTS — Detailed IDF Diagnosis")
    print(f"{'=' * 80}\n")

    low_idf_count = 0
    min_idf_gate_count = 0
    single_word_count = 0

    for rank, r in enumerate(results[:TOP_N], 1):
        src_ref = r.get("source", {}).get("ref", "")
        tgt_ref = r.get("target", {}).get("ref", "")
        score = r.get("fused_score", r.get("overall_score", r.get("score", 0)))
        channels = r.get("channels", [])

        details = compute_rarity_details(r, doc_freq_map, headword_map, total_texts)

        if details["has_low_idf"]:
            low_idf_count += 1
        if details["min_idf_gate"]:
            min_idf_gate_count += 1
        if details["single_word_penalty"]:
            single_word_count += 1

        # Format flags
        flags = []
        if details["has_low_idf"]:
            flags.append("LOW-IDF")
        if details["min_idf_gate"]:
            flags.append("MIN-GATE")
        if details["single_word_penalty"]:
            flags.append("SINGLE-WORD")
        if details["no_sig_penalty"]:
            flags.append("NO-SIG-WORDS")
        flag_str = " [" + ", ".join(flags) + "]" if flags else ""

        # Source/target text snippets
        src_text = r.get("source", {}).get("snippet", "")[:60]
        tgt_text = r.get("target", {}).get("snippet", "")[:60]

        print(f"#{rank:3d}  score={score:.6f}  {src_ref} × {tgt_ref}{flag_str}")
        if src_text:
            print(f"      src: {src_text}")
        if tgt_text:
            print(f"      tgt: {tgt_text}")
        print(f"      channels({details['n_channels']}): {', '.join(channels)}")
        print(f"      geom_idf={details['geom_mean_idf']:.3f}  "
              f"min_idf={details['min_word_idf']:.3f}  "
              f"mult={details['multiplier']:.4f}  "
              f"mult^2={details['effective_mult_squared']:.4f}  "
              f"zone={details['zone']}  "
              f"n_words={details['n_unique_words']}  "
              f"n_sig={details['n_significant_words']}")

        for wd in details["word_details"]:
            hw_info = ""
            if wd["headword"]:
                hw_info = f"  (hw={wd['headword']}, hw_df={wd['headword_df']})"
            idf_flag = " ***" if wd["idf"] < 1.0 else ""
            print(f"        {wd['lemma']:20s}  df={wd['df']:5d}  "
                  f"idf={wd['idf']:.3f}{hw_info}{idf_flag}")
        print()

    # Summary
    print(f"{'=' * 80}")
    print(f"SUMMARY (top {TOP_N})")
    print(f"{'=' * 80}")
    print(f"Results with at least one low-IDF word (< 1.0): {low_idf_count}/{TOP_N}")
    print(f"Results where min-IDF gate triggered:           {min_idf_gate_count}/{TOP_N}")
    print(f"Results with single-word penalty:               {single_word_count}/{TOP_N}")
    print()

    # Write machine-readable output
    output_path = PROJECT_ROOT / "evaluation" / "results" / "diagnostic_top_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostic_data = []
    for rank, r in enumerate(results[:TOP_N], 1):
        details = compute_rarity_details(r, doc_freq_map, headword_map, total_texts)
        diagnostic_data.append({
            "rank": rank,
            "source_ref": r.get("source", {}).get("ref", ""),
            "target_ref": r.get("target", {}).get("ref", ""),
            "score": r.get("fused_score", r.get("overall_score", r.get("score", 0))),
            "channels": r.get("channels", []),
            **details,
        })
    with open(output_path, 'w') as f:
        json.dump(diagnostic_data, f, indent=2, default=str)
    print(f"Machine-readable output: {output_path}")


if __name__ == "__main__":
    main()
