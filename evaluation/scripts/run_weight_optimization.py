#!/usr/bin/env python3
"""
Fusion Weight Optimization — Grid Search over Channel Weights (v9)

Exploits the key insight that channel results are independent of fusion
parameters: we run all 9 channels ONCE per benchmark (~10 min total),
then re-fuse with thousands of weight/bonus/penalty configurations
(milliseconds each) to find optimal settings.

Scoring formula matches production fuse_results() exactly:
  - Three-layer rarity scoring: penalty^2, IDF-weighted convergence,
    rarity boost for rare multi-channel/multi-word matches
  - Surface-form deduplication by (source_word, target_word)
  - Corrected lemma filter: not lemma.startswith('[') (not idf > 0)
  - Geometric mean corpus-IDF with named constants

Key optimizations:
  1. Extract lightweight pair summaries and discard heavy result dicts
  2. Use numpy for vectorized score computation
  3. Skip windows in sweep (appended after line results)
  4. Total recall is constant across configs

Two-phase sweep:
  Phase 2a: Sweep all weight configs with current bonus/penalty
  Phase 2b: Sweep convergence_bonus × IDF curve params with best weights

Objective: recall@500 averaged across benchmarks (weighted by gold count),
tiebreak on recall@100.

Usage:
    TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/run_weight_optimization.py
"""

import csv
import itertools
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

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
    WINDOW_CHANNELS,
    run_channel, fuse_results, merge_line_and_window, make_window_units,
    _get_corpus_doc_freqs, _get_total_texts,
)

TEXTS_DIR = PROJECT_ROOT / "texts"
BENCHMARKS_DIR = PROJECT_ROOT / "evaluation" / "benchmarks"
OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "results"

# ---------------------------------------------------------------------------
# Benchmark definitions (same as benchmark_production_fusion.py)
# ---------------------------------------------------------------------------
BENCHMARKS = [
    ("Lucan BC 1 - Vergil Aen.",
     "lucan.bellum_civile.part.1.tess",
     "vergil.aeneid.tess",
     "lucan_vergil"),
    ("VF Argon. 1 - Vergil Aen.",
     "valerius_flaccus.argonautica.part.1.tess",
     "vergil.aeneid.tess",
     "vf_vergil"),
    ("Achilleid - Vergil Aen.",
     "statius.achilleid.tess",
     "vergil.aeneid.tess",
     "achilleid_vergil"),
    ("Achilleid - Ovid Met.",
     "statius.achilleid.tess",
     "ovid.metamorphoses.tess",
     "achilleid_ovid"),
    ("Achilleid - Thebaid",
     "statius.achilleid.tess",
     "statius.thebaid.tess",
     "achilleid_thebaid"),
]

# ---------------------------------------------------------------------------
# Weight sweep grid
# ---------------------------------------------------------------------------
WEIGHT_GRID = {
    "edit_distance": [2.0, 3.0, 4.0, 5.0],
    "sound":         [1.5, 2.5, 3.0, 4.0],
    "exact":         [1.0, 2.0, 3.0],
    "lemma":         [1.0, 1.5, 2.0],
    "rare_word":     [1.0, 2.0, 3.0],
    "dictionary":    [0.5, 1.0, 1.5],
    "semantic":      [0.5, 0.8, 1.2],
    "syntax":        [0.3, 0.5, 1.0],
    "lemma_min1":    [0.1, 0.3, 0.5],
}

# Fixed channel order for numpy weight vectors
CHANNEL_NAMES = list(WEIGHT_GRID.keys())
CH_IDX = {ch: i for i, ch in enumerate(CHANNEL_NAMES)}

CONVERGENCE_GRID = [0.0, 0.25, 0.5, 0.75, 1.0]
STOPWORD_PENALTY_GRID = [0.1, 0.2, 0.3, 0.5, 1.0]  # legacy, used as idf_floor
IDF_FLOOR_GRID = [0.05, 0.1, 0.2]
IDF_THRESHOLD_GRID = [0.5, 1.0, 1.5, 2.0]
CONV_IDF_POWER_GRID = [1.0, 2.0, 3.0]  # re-enabled: u/v fix changes IDF landscape
MIN_IDF_THRESHOLD_GRID = [0.3, 0.5, 0.7, 1.0]  # re-enabled: headword normalization fixes IDF accuracy
MIN_IDF_PENALTY_GRID = [0.3, 0.5, 0.7]


def log(msg):
    """Print with immediate flush (avoids tee buffering issues)."""
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Gold standard loading
# ---------------------------------------------------------------------------

def load_gold(benchmark_key):
    """Load gold entries for a benchmark."""
    if benchmark_key == "lucan_vergil":
        path = BENCHMARKS_DIR / "lucan_vergil_lexical_benchmark.json"
        return json.load(open(path))
    elif benchmark_key == "vf_vergil":
        path = BENCHMARKS_DIR / "vf_vergil_gold.json"
        return json.load(open(path))
    elif benchmark_key.startswith("achilleid_"):
        path = BENCHMARKS_DIR / "achilleid_gold_2plus_commentators.json"
        data = json.load(open(path))
        target_map = {
            "achilleid_vergil": "vergil.aeneid.tess",
            "achilleid_ovid": "ovid.metamorphoses.tess",
            "achilleid_thebaid": "statius.thebaid.tess",
        }
        target_work = target_map.get(benchmark_key)
        if target_work:
            return [e for e in data if e.get("target_work") == target_work]
    return None


def parse_ref(ref_str):
    """Extract (book, line) from a reference string."""
    nums = [int(x) for x in re.findall(r'\d+', str(ref_str))]
    if len(nums) >= 2:
        return nums[-2], nums[-1]
    if len(nums) == 1:
        return 1, nums[0]
    return None, None


def parse_range_ref(ref_str):
    """Parse a ref that might be a range (e.g., 'luc. 1.1-luc. 1.2').
    Returns (book1, line1, book2, line2)."""
    if '-' in ref_str and ref_str.count('.') > 2:
        parts = ref_str.split('-')
        if len(parts) == 2:
            b1, l1 = parse_ref(parts[0])
            b2, l2 = parse_ref(parts[1])
            if b1 is not None and b2 is not None:
                return b1, l1, b2, l2
    b, l = parse_ref(ref_str)
    if b is not None:
        return b, l, b, l
    return None, None, None, None


def preparse_gold(gold_entries):
    """Pre-parse gold entries for fast evaluation."""
    parsed = []
    for i, g in enumerate(gold_entries):
        gs_b, gs_l = parse_ref(g["source_ref"])
        gt_b, gt_l = parse_ref(g["target_ref"])
        if gs_b is not None and gt_b is not None:
            parsed.append((i, gs_b, gs_l, gt_b, gt_l))
    return parsed


# ---------------------------------------------------------------------------
# Phase 1: Run channels and extract lightweight summaries
# ---------------------------------------------------------------------------

def extract_pair_summary(channel_results, parsed_gold, stop_words,
                         language='la'):
    """Extract lightweight pair summaries from channel results.

    Aggregates per-channel results into per-pair data:
    - Raw score per channel (9-element vector for weighted sum)
    - Channel count (for convergence bonus)
    - Mean corpus IDF (float, for graduated rarity multiplier)
    - Gold match indices (for recall evaluation)

    Returns numpy arrays for vectorized computation in the sweep.
    """
    import math

    # Step 1: Aggregate per-pair data (same logic as fuse_results, lightweight)
    pair_data = {}

    for ch_name, results in channel_results.items():
        ci = CH_IDX.get(ch_name)
        if ci is None:
            continue
        for r in results:
            src_ref = r.get("source", {}).get("ref", "")
            tgt_ref = r.get("target", {}).get("ref", "")
            key = (src_ref, tgt_ref)

            if key not in pair_data:
                pair_data[key] = {
                    "scores": [0.0] * len(CHANNEL_NAMES),
                    "n_ch": 0,
                    "matched_words": {},
                }

            raw_score = r.get("overall_score") or r.get("score") or 0
            pair_data[key]["scores"][ci] = raw_score
            pair_data[key]["n_ch"] += 1

            # Accumulate matched words for rarity computation
            for mw in r.get("matched_words", []):
                lemma = mw.get("lemma", "")
                if lemma and lemma not in pair_data[key]["matched_words"]:
                    pair_data[key]["matched_words"][lemma] = mw

    # Step 1b: Batch-fetch corpus document frequencies for all unique lemmas
    # Include all lexical entries (not just idf>0) — rare_word, semantic,
    # dictionary channels produce valid lemma matches with idf=0. Only
    # exclude sub-lexical fragments (keys starting with '[').
    all_lemmas = set()
    for data in pair_data.values():
        for lemma in data["matched_words"]:
            if lemma and not lemma.startswith('['):
                all_lemmas.add(lemma)

    log(f"    Fetching corpus doc frequencies for {len(all_lemmas):,} lemmas...")
    total_texts = _get_total_texts(language)
    corpus_dfs = _get_corpus_doc_freqs(list(all_lemmas), language)
    log(f"    -> total_texts={total_texts}, fetched {len(corpus_dfs)} DFs")
    _log_total = math.log(total_texts)

    # Step 2: Build numpy arrays
    N = len(pair_data)
    C = len(CHANNEL_NAMES)

    scores_matrix = np.zeros((N, C), dtype=np.float64)
    n_channels = np.zeros(N, dtype=np.float64)
    rarity_mean_idfs = np.zeros(N, dtype=np.float64)
    rarity_min_idfs = np.zeros(N, dtype=np.float64)
    n_unique_words_arr = np.zeros(N, dtype=np.float64)
    n_significant_words_arr = np.zeros(N, dtype=np.float64)
    gold_matches = []

    for i, ((src_ref, tgt_ref), data) in enumerate(pair_data.items()):
        scores_matrix[i] = data["scores"]
        # Count only channels with raw_score > 0 for convergence bonus.
        n_channels[i] = sum(1 for s in data["scores"] if s > 0)

        # Compute corpus IDFs with surface-form deduplication.
        # Group by (source_word, target_word) and keep highest-df entry
        # to prevent inflected forms (e.g., "pugnas" df=1) from inflating
        # the geometric mean when canonical lemma ("pugna" df=596) is present.
        mw = data["matched_words"]
        word_pair_best = {}  # (src_word, tgt_word) -> (corpus_idf, df)
        unique_src_words = set()
        unique_tgt_words = set()
        for lemma, info in mw.items():
            if lemma.startswith('['):
                continue  # sub-lexical fragment
            df = corpus_dfs.get(lemma, 0)
            if df <= 0:
                continue  # not in inverted index
            cidf = _log_total - math.log(df)
            sw = info.get('source_word', '')
            tw = info.get('target_word', '')
            word_key = (sw, tw) if (sw or tw) else (lemma,)
            existing = word_pair_best.get(word_key)
            if existing is None or df > existing[1]:
                word_pair_best[word_key] = (cidf, df)
            unique_src_words.add(sw.lower() if sw else lemma)
            unique_tgt_words.add(tw.lower() if tw else lemma)
        corpus_idfs = [cidf for cidf, _ in word_pair_best.values()]

        if corpus_idfs:
            # Geometric mean (sensitive to individual ultra-common words)
            log_sum = sum(math.log(max(idf, 0.001)) for idf in corpus_idfs)
            rarity_mean_idfs[i] = math.exp(log_sum / len(corpus_idfs))
            rarity_min_idfs[i] = min(corpus_idfs)
            # True unique word count = min of source-side and target-side
            n_unique_words_arr[i] = min(len(unique_src_words), len(unique_tgt_words))
            # Significant words: those with IDF at or above the rarity
            # threshold. Used to detect "all common words" bigrams.
            n_significant_words_arr[i] = sum(
                1 for cidf, _ in word_pair_best.values()
                if cidf >= RARITY_IDF_THRESHOLD
            )
        else:
            # No recognized lexical lemmas (all sub-lexical fragments from
            # sound/edit_distance, or df=0). Treat as common-word match —
            # absence of lexical evidence should not be rewarded.
            rarity_mean_idfs[i] = 0.0
            rarity_min_idfs[i] = 0.0
            n_unique_words_arr[i] = 0
            n_significant_words_arr[i] = 0

        # Gold matching (precompute which gold entries this pair covers)
        src_b1, src_l1, src_b2, src_l2 = parse_range_ref(src_ref)
        tgt_b1, tgt_l1, tgt_b2, tgt_l2 = parse_range_ref(tgt_ref)
        matched = frozenset()
        if src_b1 is not None and tgt_b1 is not None:
            m = set()
            for gi, gs_b, gs_l, gt_b, gt_l in parsed_gold:
                source_match = (gs_b == src_b1 and src_l1 <= gs_l <= src_l2)
                target_match = (gt_b == tgt_b1 and
                               tgt_l1 - 3 <= gt_l <= tgt_l2 + 3)
                if source_match and target_match:
                    m.add(gi)
            matched = frozenset(m)
        gold_matches.append(matched)

    return {
        "scores_matrix": scores_matrix,
        "n_channels": n_channels,
        "rarity_mean_idfs": rarity_mean_idfs,
        "rarity_min_idfs": rarity_min_idfs,
        "n_unique_words": n_unique_words_arr,
        "n_significant_words": n_significant_words_arr,
        "gold_matches": gold_matches,
        "n_pairs": N,
    }


def run_channels_and_extract(benchmarks, tp, matcher, scorer):
    """Run all channels per benchmark, extract lightweight summaries.

    Processes one benchmark at a time to keep memory low — heavy channel
    results are discarded after summary extraction.

    Returns:
        summaries: dict of bench_key → pair summary (numpy arrays)
        total_recall_info: dict of bench_key → {n_gold, total_found}
    """
    from backend.matcher import DEFAULT_LATIN_STOP_WORDS, DEFAULT_GREEK_STOP_WORDS
    stop_words = DEFAULT_LATIN_STOP_WORDS | DEFAULT_GREEK_STOP_WORDS

    summaries = {}
    total_recall_info = {}

    for display_name, source_file, target_file, bench_key in benchmarks:
        log(f"\n{'='*70}")
        log(f"  {display_name}")
        log(f"{'='*70}")

        # Load gold
        gold_entries = load_gold(bench_key)
        if gold_entries is None:
            log(f"  ERROR: Could not load gold for {bench_key}")
            continue
        parsed_gold = preparse_gold(gold_entries)
        n_gold = len(parsed_gold)
        log(f"  Gold entries: {len(gold_entries)} ({n_gold} parseable)")

        # Load text units
        source_path = TEXTS_DIR / "la" / source_file
        target_path = TEXTS_DIR / "la" / target_file
        if not source_path.exists() or not target_path.exists():
            log(f"  ERROR: Text file not found")
            continue

        log(f"  Processing source: {source_file}")
        source_units = tp.process_file(str(source_path), "la", "line")
        log(f"  -> {len(source_units)} source units")

        log(f"  Processing target: {target_file}")
        target_units = tp.process_file(str(target_path), "la", "line")
        log(f"  -> {len(target_units)} target units")

        # Build configs
        configs = {}
        for name, cfg in CHANNEL_CONFIGS.items():
            c = dict(cfg)
            if "language" in c:
                c["language"] = "la"
            configs[name] = c

        # --- Line-level: all 9 channels ---
        line_channel_results = {}
        line_channels = [ch for ch in CHANNEL_ORDER if ch in configs]
        t0 = time.time()

        for i, ch_name in enumerate(line_channels):
            ch_t0 = time.time()
            results = run_channel(
                ch_name, configs[ch_name], source_units, target_units,
                matcher, scorer, source_file, target_file,
                source_path=str(source_path), target_path=str(target_path),
            )
            count = len(results) if results else 0
            elapsed = time.time() - ch_t0
            log(f"    [line] {i+1}/{len(line_channels)} {ch_name}: "
                f"{count:,} results ({elapsed:.1f}s)")
            if results:
                line_channel_results[ch_name] = results

        # --- Window-level (for total recall computation only) ---
        window_channel_results = {}
        source_windows = make_window_units(source_units)
        target_windows = make_window_units(target_units)
        window_channels = [ch for ch in WINDOW_CHANNELS if ch in configs]

        for i, ch_name in enumerate(window_channels):
            ch_t0 = time.time()
            results = run_channel(
                ch_name, configs[ch_name], source_windows, target_windows,
                matcher, scorer, source_file, target_file,
                source_path=str(source_path), target_path=str(target_path),
            )
            count = len(results) if results else 0
            elapsed = time.time() - ch_t0
            log(f"    [window] {i+1}/{len(window_channels)} {ch_name}: "
                f"{count:,} results ({elapsed:.1f}s)")
            if results:
                window_channel_results[ch_name] = results

        total_elapsed = time.time() - t0
        log(f"  Channels complete: {total_elapsed:.1f}s")

        # Compute total recall ONCE (it's constant across all configs)
        line_fused = fuse_results(line_channel_results)
        window_fused = fuse_results(window_channel_results)
        merged_full = merge_line_and_window(line_fused, window_fused)

        # Count gold found in full results
        gold_found_total = set()
        for result in merged_full:
            src_ref = result.get("source", {}).get("ref", "")
            tgt_ref = result.get("target", {}).get("ref", "")
            sb1, sl1, sb2, sl2 = parse_range_ref(src_ref)
            tb1, tl1, tb2, tl2 = parse_range_ref(tgt_ref)
            if sb1 is not None and tb1 is not None:
                for gi, gs_b, gs_l, gt_b, gt_l in parsed_gold:
                    if gi in gold_found_total:
                        continue
                    if (gs_b == sb1 and sl1 <= gs_l <= sl2 and
                            gt_b == tb1 and tl1 - 3 <= gt_l <= tl2 + 3):
                        gold_found_total.add(gi)

        total_recall_info[bench_key] = {
            "n_gold": n_gold,
            "total_found": len(gold_found_total),
            "total_recall": len(gold_found_total) / n_gold if n_gold > 0 else 0,
        }
        log(f"  Total recall: {len(gold_found_total)}/{n_gold} "
            f"({len(gold_found_total)/n_gold:.1%})")

        # Extract lightweight line-pair summary (for the sweep)
        log(f"  Extracting pair summaries...")
        summary = extract_pair_summary(line_channel_results, parsed_gold,
                                       stop_words)
        summary["n_gold"] = n_gold
        summary["display_name"] = display_name
        summaries[bench_key] = summary
        log(f"  -> {summary['n_pairs']:,} unique pairs, "
            f"{len([g for g in summary['gold_matches'] if g]):,} gold-matching")

        # Discard heavy results — only keep lightweight summaries
        del line_channel_results, window_channel_results
        del line_fused, window_fused, merged_full

    return summaries, total_recall_info


# ---------------------------------------------------------------------------
# Phase 2: Fast grid sweep (numpy-based)
# ---------------------------------------------------------------------------

def weights_to_vector(weights):
    """Convert weights dict to numpy vector in CHANNEL_NAMES order."""
    return np.array([weights[ch] for ch in CHANNEL_NAMES], dtype=np.float64)


def generate_weight_configs():
    """Generate all weight combinations from the grid."""
    keys = list(WEIGHT_GRID.keys())
    value_lists = [WEIGHT_GRID[k] for k in keys]
    configs = []
    for values in itertools.product(*value_lists):
        configs.append(dict(zip(keys, values)))
    return configs


def evaluate_config_fast(summaries, weight_vector, bonus, idf_floor,
                         idf_threshold, conv_idf_power=1.0,
                         min_idf_threshold=0.0, min_idf_penalty=1.0,
                         penalty_power=None, boost_weight=None,
                         boost_cap=None,
                         k_values=(100, 500)):
    """Evaluate a single config across all benchmarks.

    Matches the production scoring formula in fuse_results() exactly:
      base = scores_matrix @ weight_vector
      mult = piecewise_linear(geom_mean_idf, idf_floor, idf_threshold)
      Layer 3: mult > 1.0 for rare multi-channel/multi-word matches
      idf_weight = min(1.0, geom_mean_idf)^2                   [Layer 2]
      weighted_n = n_channels * idf_weight                      [Layer 2]
      conv = bonus * max(0, weighted_n - 1)                     [Layer 2]
      fused = base * mult^penalty_power + conv * mult^conv_power

    Returns dict with recall@K metrics.
    """
    if penalty_power is None:
        penalty_power = RARITY_PENALTY_POWER
    if boost_weight is None:
        boost_weight = RARITY_BOOST_WEIGHT
    if boost_cap is None:
        boost_cap = RARITY_BOOST_CAP
    _cutoff = RARITY_NEAR_STOPWORD_CUTOFF
    _ramp_offset = RARITY_RAMP_OFFSET

    total_gold = 0
    found_at_k = defaultdict(int)
    max_k = max(k_values)
    k_set = set(k_values)

    for bench_key, s in summaries.items():
        sm = s["scores_matrix"]
        nc = s["n_channels"]
        mean_idfs = s["rarity_mean_idfs"]
        min_idfs = s["rarity_min_idfs"]
        n_words = s["n_unique_words"]
        n_sig = s["n_significant_words"]
        gm = s["gold_matches"]
        n_gold = s["n_gold"]
        total_gold += n_gold
        N = s["n_pairs"]

        # Vectorized score computation
        base = sm @ weight_vector

        # IDF-weighted convergence (Layer 2): weight each channel's
        # contribution by min(1.0, min_word_idf)^2 — continuous Zipf-like
        # scaling gated by the WEAKEST word in the pair.
        idf_weights = np.minimum(1.0, min_idfs) ** 2
        weighted_nc = nc * idf_weights
        # Hard zeroing for single-word and no-sig matches.
        no_signal_mask = (n_words <= 1) | (n_sig == 0)
        weighted_nc = np.where(no_signal_mask, 0.0, weighted_nc)
        conv = bonus * np.maximum(0.0, weighted_nc - 1.0)

        # Graduated IDF multiplier (vectorized piecewise linear)
        ramp_start = idf_floor + _ramp_offset
        t = (mean_idfs - _cutoff) / (idf_threshold - _cutoff)
        ramp_values = ramp_start + t * (1.0 - ramp_start)

        # Layer 3: Rarity boost for rare multi-channel/multi-word matches.
        # Requires both channel_factor > 0 and word_factor > 0.
        channel_factor = np.minimum(1.0, (nc - 1.0) / 5.0)
        word_factor = np.minimum(1.0, (n_words - 1.0) / 3.0)
        boost_factor = np.minimum(channel_factor, word_factor)
        # Log-curve boost: 1.0 + weight * factor * log(geom_idf / threshold)
        log_ratio = np.log(np.maximum(mean_idfs / idf_threshold, 1e-10))
        boost_mult = np.minimum(boost_cap,
                                1.0 + boost_weight * boost_factor * log_ratio)
        # Only apply boost when geom_idf >= threshold (otherwise use penalty)
        boost_mult = np.maximum(boost_mult, 1.0)  # floor at 1.0 for boost zone

        multipliers = np.where(
            mean_idfs < _cutoff, idf_floor,
            np.where(mean_idfs < idf_threshold, ramp_values, boost_mult))

        # Single-word penalty: demote matches sharing only one word
        single_word_mask = n_words <= 1
        multipliers = np.where(single_word_mask,
                               multipliers * SINGLE_WORD_PENALTY, multipliers)
        # No-significant-words penalty: milder penalty for multi-word
        # matches where no word has IDF >= threshold
        no_sig_mask = (n_words > 1) & (n_sig == 0)
        multipliers = np.where(no_sig_mask,
                               multipliers * NO_SIGNIFICANT_WORDS_PENALTY,
                               multipliers)

        # Min-IDF gate: if ANY lemma's corpus IDF < threshold, extra penalty
        if min_idf_threshold > 0 and min_idf_penalty < 1.0:
            min_idf_mask = min_idfs < min_idf_threshold
            multipliers = np.where(min_idf_mask,
                                   multipliers * min_idf_penalty, multipliers)

        # Apply rarity multiplier with penalty power (Layer 1):
        #   fused = base * mult^penalty_power + conv * mult^conv_power
        conv_multipliers = np.power(multipliers, conv_idf_power)
        fused = base * np.power(multipliers, penalty_power) + conv * conv_multipliers

        # Get top-K indices efficiently
        actual_k = min(max_k, N)
        if N > actual_k * 2:
            # argpartition is O(N), much faster than full argsort for large N
            top_idx = np.argpartition(-fused, actual_k)[:actual_k]
            top_sorted = top_idx[np.argsort(-fused[top_idx])]
        else:
            top_sorted = np.argsort(-fused)[:actual_k]

        # Walk through ranked pairs, accumulate gold hits
        gold_found = set()
        for rank_0 in range(actual_k):
            pair_idx = top_sorted[rank_0]
            gm_i = gm[pair_idx]
            if gm_i:  # skip empty frozensets (most pairs)
                gold_found |= gm_i
            rank = rank_0 + 1
            if rank in k_set:
                found_at_k[rank] += len(gold_found)

    metrics = {"total_gold": total_gold}
    for k in k_values:
        metrics[f"found_at_{k}"] = found_at_k[k]
        metrics[f"recall_at_{k}"] = (
            found_at_k[k] / total_gold if total_gold > 0 else 0
        )
    return metrics


def run_weight_sweep(summaries, convergence_bonus, idf_floor, idf_threshold,
                     conv_idf_power=1.0, min_idf_threshold=0.0,
                     min_idf_penalty=1.0):
    """Phase 2a: Sweep all weight configs with fixed bonus/IDF params."""
    weight_configs = generate_weight_configs()
    total = len(weight_configs)
    log(f"\nPhase 2a: Sweeping {total:,} weight configurations...")
    log(f"  Fixed: convergence_bonus={convergence_bonus}, "
        f"idf_floor={idf_floor}, idf_threshold={idf_threshold}, "
        f"conv_idf_power={conv_idf_power}, "
        f"min_idf_threshold={min_idf_threshold}, "
        f"min_idf_penalty={min_idf_penalty}")

    results = []
    t0 = time.time()
    last_report = t0

    for i, weights in enumerate(weight_configs):
        wv = weights_to_vector(weights)
        metrics = evaluate_config_fast(
            summaries, wv, convergence_bonus, idf_floor, idf_threshold,
            conv_idf_power=conv_idf_power,
            min_idf_threshold=min_idf_threshold,
            min_idf_penalty=min_idf_penalty,
            k_values=(100, 500),
        )
        results.append((weights, metrics))

        # Progress report every 3 minutes or every 5000 configs
        now = time.time()
        if now - last_report >= 180 or (i + 1) % 5000 == 0 or i + 1 == total:
            elapsed = now - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate if rate > 0 else 0
            best_so_far = max(results, key=lambda x: _objective(x[1]))
            best_r500 = best_so_far[1].get("recall_at_500", 0)
            log(f"  [{i+1:,}/{total:,}] {elapsed:.0f}s elapsed, "
                f"{rate:.0f} configs/s, ETA {eta:.0f}s — "
                f"best R@500 so far: {best_r500:.1%}")
            last_report = now

    results.sort(key=lambda x: _objective(x[1]), reverse=True)
    elapsed = time.time() - t0
    log(f"  Weight sweep complete: {total:,} configs in {elapsed:.1f}s")
    return results


def run_bonus_idf_sweep(summaries, best_weights):
    """Phase 2b: Sweep convergence_bonus × idf_floor × idf_threshold × min-IDF params."""
    combos = list(itertools.product(
        CONVERGENCE_GRID, IDF_FLOOR_GRID, IDF_THRESHOLD_GRID,
        CONV_IDF_POWER_GRID,
        MIN_IDF_THRESHOLD_GRID, MIN_IDF_PENALTY_GRID))
    total = len(combos)
    log(f"\nPhase 2b: Sweeping {total} bonus × idf_floor × idf_threshold "
        f"× conv_power × min_idf_thresh × min_idf_pen configs...")

    wv = weights_to_vector(best_weights)
    results = []
    for bonus, idf_floor, idf_threshold, conv_power, mit, mip in combos:
        metrics = evaluate_config_fast(
            summaries, wv, bonus, idf_floor, idf_threshold,
            conv_idf_power=conv_power,
            min_idf_threshold=mit, min_idf_penalty=mip,
            k_values=(100, 500),
        )
        results.append((bonus, idf_floor, idf_threshold, conv_power,
                         mit, mip, metrics))

    results.sort(key=lambda x: _objective(x[6]), reverse=True)
    log(f"  Bonus/IDF sweep complete: {total} configs")
    return results


def _objective(metrics):
    """Objective function: (recall@500, recall@100) for sorting."""
    r500 = metrics.get("recall_at_500", 0)
    r100 = metrics.get("recall_at_100", 0)
    return (r500, r100)


# ---------------------------------------------------------------------------
# Phase 3: Output
# ---------------------------------------------------------------------------

def format_weights(weights):
    """Format weights dict as compact string."""
    return " ".join(f"{k}={weights[k]}" for k in CHANNEL_NAMES)


def format_weights_short(weights):
    """Format weights as a compact abbreviation."""
    abbrev = ["ed", "sn", "ex", "lm", "rw", "dc", "se", "sy", "m1"]
    return "/".join(f"{a}{weights[k]}" for a, k in zip(abbrev, CHANNEL_NAMES))


def print_top_configs(weight_results, bonus_idf_results, summaries,
                      total_recall_info,
                      current_weights, current_bonus,
                      current_idf_floor, current_idf_threshold,
                      current_conv_idf_power=1.0):
    """Print summary of top configurations."""
    log(f"\n\n{'='*80}")
    log("OPTIMIZATION RESULTS")
    log(f"{'='*80}")

    # Total recall (constant across all configs)
    total_gold_all = sum(v["n_gold"] for v in total_recall_info.values())
    total_found_all = sum(v["total_found"] for v in total_recall_info.values())
    log(f"\nTotal recall (constant, all configs): "
        f"{total_found_all}/{total_gold_all} "
        f"({total_found_all/total_gold_all:.1%})")
    for bk, info in total_recall_info.items():
        log(f"  {bk}: {info['total_found']}/{info['n_gold']} "
            f"({info['total_recall']:.1%})")

    # Current config baseline
    wv_current = weights_to_vector(current_weights)
    current_metrics = evaluate_config_fast(
        summaries, wv_current, current_bonus,
        current_idf_floor, current_idf_threshold,
        conv_idf_power=current_conv_idf_power,
        min_idf_threshold=RARITY_MIN_IDF_THRESHOLD,
        min_idf_penalty=RARITY_MIN_IDF_PENALTY,
        k_values=(10, 50, 100, 500, 1000, 5000),
    )
    log(f"\n--- Current Config K (baseline) ---")
    log(f"  Weights: {format_weights(current_weights)}")
    log(f"  Bonus: {current_bonus}, IDF floor: {current_idf_floor}, "
        f"IDF threshold: {current_idf_threshold}, "
        f"conv_idf_power: {current_conv_idf_power}, "
        f"min_idf_threshold: {RARITY_MIN_IDF_THRESHOLD}, "
        f"min_idf_penalty: {RARITY_MIN_IDF_PENALTY}")
    for k in [10, 50, 100, 500, 1000, 5000]:
        key = f"recall_at_{k}"
        fkey = f"found_at_{k}"
        if key in current_metrics:
            log(f"  R@{k}: {current_metrics[key]:.1%} "
                f"({current_metrics[fkey]}/{current_metrics['total_gold']})")

    # Top weight configs (Phase 2a)
    log(f"\n--- Top 20 Weight Configs (Phase 2a) ---")
    log(f"{'Rank':>4} {'R@500':>8} {'R@100':>8} {'F@500':>6} {'F@100':>6}  Weights")
    log("-" * 110)

    for rank, (weights, metrics) in enumerate(weight_results[:20], 1):
        r500 = metrics.get("recall_at_500", 0)
        r100 = metrics.get("recall_at_100", 0)
        f500 = metrics.get("found_at_500", 0)
        f100 = metrics.get("found_at_100", 0)
        is_current = (weights == current_weights)
        marker = " <-- CURRENT" if is_current else ""
        log(f"{rank:>4} {r500:>7.1%} {r100:>7.1%}  {f500:>5} {f100:>5}  "
            f"{format_weights_short(weights)}{marker}")

    # Best weight config details
    best_weights, best_metrics = weight_results[0]
    log(f"\n--- Best Weight Config (Phase 2a) ---")
    log(f"  {format_weights(best_weights)}")
    log(f"  R@500: {best_metrics.get('recall_at_500', 0):.1%} "
        f"({best_metrics.get('found_at_500', 0)}/{best_metrics['total_gold']}), "
        f"R@100: {best_metrics.get('recall_at_100', 0):.1%} "
        f"({best_metrics.get('found_at_100', 0)}/{best_metrics['total_gold']})")

    log(f"\n  Weight changes from Config K:")
    any_change = False
    for k in CHANNEL_NAMES:
        if best_weights[k] != current_weights[k]:
            log(f"    {k}: {current_weights[k]} -> {best_weights[k]}")
            any_change = True
    if not any_change:
        log(f"    (no changes — current weights are optimal)")

    # Top bonus/IDF configs (Phase 2b)
    if bonus_idf_results:
        log(f"\n--- Top 10 Bonus x IDF x MinIDF Configs (Phase 2b) ---")
        log(f"{'Rank':>4} {'Bonus':>6} {'Floor':>6} {'Thresh':>6} {'CvPow':>5} "
            f"{'MinTh':>6} {'MinPn':>6} {'R@500':>8} {'R@100':>8} "
            f"{'F@500':>5} {'F@100':>5}")
        log("-" * 100)

        for rank, entry in enumerate(bonus_idf_results[:10], 1):
            bonus, idf_floor, idf_threshold, conv_power, mit, mip, metrics = entry
            r500 = metrics.get("recall_at_500", 0)
            r100 = metrics.get("recall_at_100", 0)
            f500 = metrics.get("found_at_500", 0)
            f100 = metrics.get("found_at_100", 0)
            log(f"{rank:>4} {bonus:>6.2f} {idf_floor:>6.2f} "
                f"{idf_threshold:>6.2f} {conv_power:>5.1f} "
                f"{mit:>6.2f} {mip:>6.2f} {r500:>7.1%} "
                f"{r100:>7.1%}  {f500:>4} {f100:>4}")

    # Final recommendation
    if bonus_idf_results:
        (best_bonus, best_floor, best_thresh, best_conv_power,
         best_mit, best_mip, best_bp_metrics) = bonus_idf_results[0]
    else:
        best_bonus = current_bonus
        best_floor = current_idf_floor
        best_thresh = current_idf_threshold
        best_conv_power = 1.0
        best_mit = RARITY_MIN_IDF_THRESHOLD
        best_mip = RARITY_MIN_IDF_PENALTY

    log(f"\n--- RECOMMENDATION ---")
    log(f"  Weights: {format_weights(best_weights)}")
    log(f"  Convergence bonus: {best_bonus}")
    log(f"  IDF floor: {best_floor}")
    log(f"  IDF threshold: {best_thresh}")
    log(f"  Convergence IDF power: {best_conv_power}")
    log(f"  Min-IDF threshold: {best_mit}")
    log(f"  Min-IDF penalty: {best_mip}")

    # Full evaluation of recommended config
    wv_best = weights_to_vector(best_weights)
    final_metrics = evaluate_config_fast(
        summaries, wv_best, best_bonus, best_floor, best_thresh,
        conv_idf_power=best_conv_power,
        min_idf_threshold=best_mit, min_idf_penalty=best_mip,
        k_values=(10, 50, 100, 500, 1000, 5000),
    )
    log(f"\n  Recall@K for recommended config:")
    for k in [10, 50, 100, 500, 1000, 5000]:
        key = f"recall_at_{k}"
        fkey = f"found_at_{k}"
        if key in final_metrics:
            log(f"    R@{k}: {final_metrics[key]:.1%} "
                f"({final_metrics[fkey]}/{final_metrics['total_gold']})")

    # Improvement over current
    curr_r500 = current_metrics.get("recall_at_500", 0)
    rec_r500 = final_metrics.get("recall_at_500", 0)
    curr_r100 = current_metrics.get("recall_at_100", 0)
    rec_r100 = final_metrics.get("recall_at_100", 0)
    log(f"\n  Improvement over Config K:")
    log(f"    R@500: {curr_r500:.1%} -> {rec_r500:.1%} "
        f"({rec_r500 - curr_r500:+.1%})")
    log(f"    R@100: {curr_r100:.1%} -> {rec_r100:.1%} "
        f"({rec_r100 - curr_r100:+.1%})")


def save_csv(weight_results, bonus_idf_results, output_dir):
    """Save all results to CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "weight_sweep_results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        header = (
            ["rank", "recall_at_500", "recall_at_100",
             "found_at_500", "found_at_100", "total_gold"]
            + list(WEIGHT_GRID.keys())
        )
        writer.writerow(header)
        for rank, (weights, metrics) in enumerate(weight_results, 1):
            row = [
                rank,
                f"{metrics.get('recall_at_500', 0):.4f}",
                f"{metrics.get('recall_at_100', 0):.4f}",
                metrics.get("found_at_500", 0),
                metrics.get("found_at_100", 0),
                metrics.get("total_gold", 0),
            ] + [weights[k] for k in WEIGHT_GRID.keys()]
            writer.writerow(row)
    log(f"\n  Weight sweep CSV: {csv_path}")
    log(f"    ({len(weight_results):,} rows)")

    if bonus_idf_results:
        csv_path2 = output_dir / "bonus_idf_sweep_results.csv"
        with open(csv_path2, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "rank", "convergence_bonus", "idf_floor", "idf_threshold",
                "conv_idf_power", "min_idf_threshold", "min_idf_penalty",
                "recall_at_500", "recall_at_100",
                "found_at_500", "found_at_100", "total_gold",
            ])
            for rank, entry in enumerate(bonus_idf_results, 1):
                bonus, idf_floor, idf_threshold, conv_power, mit, mip, metrics = entry
                writer.writerow([
                    rank, bonus, idf_floor, idf_threshold, conv_power,
                    mit, mip,
                    f"{metrics.get('recall_at_500', 0):.4f}",
                    f"{metrics.get('recall_at_100', 0):.4f}",
                    metrics.get("found_at_500", 0),
                    metrics.get("found_at_100", 0),
                    metrics.get("total_gold", 0),
                ])
        log(f"  Bonus/IDF CSV: {csv_path2}")
        log(f"    ({len(bonus_idf_results)} rows)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    t_start = time.time()

    log("=" * 80)
    log("FUSION WEIGHT OPTIMIZATION (v9 — synced with Config K production formula)")
    log("Grid search over channel weights, convergence bonus, IDF curve params,")
    log("and conv_idf_power. Uses three-layer rarity scoring: penalty^2, IDF-weighted")
    log("convergence, and rarity boost for rare multi-channel/multi-word matches.")
    log("=" * 80)

    weight_configs = generate_weight_configs()
    idf_combos = (len(CONVERGENCE_GRID) * len(IDF_FLOOR_GRID)
                  * len(IDF_THRESHOLD_GRID) * len(CONV_IDF_POWER_GRID)
                  * len(MIN_IDF_THRESHOLD_GRID) * len(MIN_IDF_PENALTY_GRID))
    log(f"\nSearch space:")
    log(f"  Weight configs: {len(weight_configs):,}")
    log(f"  Bonus x IDF params x min-IDF params: {idf_combos}")
    log(f"  Total (two-phase): {len(weight_configs):,} + {idf_combos}")
    log(f"\nCurrent Config K:")
    log(f"  {format_weights(CHANNEL_WEIGHTS)}")
    log(f"  convergence_bonus={CONVERGENCE_BONUS}, "
        f"idf_floor={RARITY_IDF_FLOOR}, idf_threshold={RARITY_IDF_THRESHOLD}, "
        f"conv_idf_power={CONVERGENCE_IDF_POWER}")
    log(f"  min_idf_threshold={RARITY_MIN_IDF_THRESHOLD}, "
        f"min_idf_penalty={RARITY_MIN_IDF_PENALTY}")
    log(f"  NOTE: df=0 entries (surface forms) now SKIPPED in geometric mean")

    # Initialize components
    log(f"\nInitializing TextProcessor, Matcher, Scorer...")
    tp = TextProcessor()
    matcher = Matcher()
    scorer = Scorer()

    # Phase 1: Run channels + extract lightweight summaries
    log(f"\n{'='*80}")
    log("PHASE 1: Run channels and extract pair summaries")
    log(f"{'='*80}")
    summaries, total_recall_info = run_channels_and_extract(
        BENCHMARKS, tp, matcher, scorer
    )
    t_phase1 = time.time()
    log(f"\nPhase 1 complete: {t_phase1 - t_start:.1f}s")
    log(f"  Benchmarks: {len(summaries)}")
    total_pairs = sum(s["n_pairs"] for s in summaries.values())
    total_gold = sum(s["n_gold"] for s in summaries.values())
    log(f"  Total unique pairs: {total_pairs:,}")
    log(f"  Total gold entries: {total_gold}")

    # Memory estimate
    mem_mb = sum(
        s["scores_matrix"].nbytes + s["n_channels"].nbytes
        + s["rarity_mean_idfs"].nbytes
        for s in summaries.values()
    ) / 1e6
    log(f"  Summary memory (arrays): {mem_mb:.1f} MB")

    # Phase 2a: Weight sweep (with current IDF params)
    log(f"\n{'='*80}")
    log("PHASE 2a: Weight grid sweep (numpy-accelerated)")
    log(f"{'='*80}")
    weight_results = run_weight_sweep(
        summaries, CONVERGENCE_BONUS, RARITY_IDF_FLOOR, RARITY_IDF_THRESHOLD,
        conv_idf_power=CONVERGENCE_IDF_POWER,
        min_idf_threshold=RARITY_MIN_IDF_THRESHOLD,
        min_idf_penalty=RARITY_MIN_IDF_PENALTY,
    )

    # Phase 2b: Bonus/IDF/min-IDF sweep with best weights
    log(f"\n{'='*80}")
    log("PHASE 2b: Bonus x IDF x min-IDF sweep")
    log(f"{'='*80}")
    best_weights = weight_results[0][0]
    bonus_idf_results = run_bonus_idf_sweep(summaries, best_weights)

    # Phase 3: Output
    log(f"\n{'='*80}")
    log("PHASE 3: Results")
    log(f"{'='*80}")
    print_top_configs(
        weight_results, bonus_idf_results, summaries,
        total_recall_info,
        CHANNEL_WEIGHTS, CONVERGENCE_BONUS,
        RARITY_IDF_FLOOR, RARITY_IDF_THRESHOLD,
        current_conv_idf_power=CONVERGENCE_IDF_POWER,
    )
    save_csv(weight_results, bonus_idf_results, OUTPUT_DIR)

    total_elapsed = time.time() - t_start
    log(f"\n\nTotal elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    log("Done.")


if __name__ == "__main__":
    main()
