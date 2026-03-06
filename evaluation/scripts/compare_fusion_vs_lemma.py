#!/usr/bin/env python3
"""
Compare fusion search vs ordinary lemma search on Aen.7 × Punica 2.

For each of the top 1000 lemma results, shows where that same (source, target)
line pair appears in the fusion ranking. Identifies quality lemma hits that
are buried in fusion results.

Usage:
    TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/compare_fusion_vs_lemma.py
"""

import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.fusion import run_fusion_search

TEXTS_DIR = PROJECT_ROOT / "texts"

SOURCE_FILE = os.environ.get("SOURCE_FILE", "vergil.aeneid.part.7.tess")
TARGET_FILE = os.environ.get("TARGET_FILE", "silius_italicus.punica.part.2.tess")
TOP_N = int(os.environ.get("TOP_N", "1000"))
LANGUAGE = os.environ.get("LANGUAGE", "la")


def find_text_path(filename):
    for p in TEXTS_DIR.rglob(filename):
        return p
    return None


def get_ref(result):
    """Extract (source_ref, target_ref) from either fusion or lemma result."""
    src = result.get("source", {})
    tgt = result.get("target", {})
    return (src.get("ref", ""), tgt.get("ref", ""))


def get_score(result):
    """Get score from either fusion or lemma result."""
    return result.get("overall_score", result.get("score", 0))


def get_matched_words(result):
    """Extract matched word lemmas from a lemma result."""
    words = []
    mw = result.get("matched_words", [])
    for w in mw:
        if isinstance(w, dict):
            words.append(w.get("lemma", w.get("target_word", "?")))
        elif isinstance(w, str):
            words.append(w)
    return words


def main():
    print("=" * 78)
    print("FUSION vs LEMMA COMPARISON")
    print(f"Source: {SOURCE_FILE}")
    print(f"Target: {TARGET_FILE}")
    print(f"Top N:  {TOP_N}")
    print("=" * 78)

    # Find text files
    src_path = find_text_path(SOURCE_FILE)
    tgt_path = find_text_path(TARGET_FILE)
    if not src_path or not tgt_path:
        print(f"ERROR: Could not find text files")
        return

    # Initialize
    print("\nInitializing components...")
    tp = TextProcessor()
    matcher = Matcher()
    scorer = Scorer()

    # Process texts
    print(f"Processing {SOURCE_FILE}...")
    source_units = tp.process_file(str(src_path), LANGUAGE, 'line')
    print(f"  -> {len(source_units)} lines")
    print(f"Processing {TARGET_FILE}...")
    target_units = tp.process_file(str(tgt_path), LANGUAGE, 'line')
    print(f"  -> {len(target_units)} lines")

    # 1) Run fusion search
    print("\n--- Running fusion search ---")
    t0 = time.time()
    fusion_results = run_fusion_search(
        source_units=source_units,
        target_units=target_units,
        matcher=matcher, scorer=scorer,
        source_id=SOURCE_FILE, target_id=TARGET_FILE,
        source_path=str(src_path), target_path=str(tgt_path),
        mode="merged", max_results=0,
        language=LANGUAGE
    )
    fusion_time = time.time() - t0
    print(f"  Fusion: {len(fusion_results)} results in {fusion_time:.1f}s")

    # 2) Run lemma search (V3-style)
    print("\n--- Running lemma search (V3-style) ---")
    t0 = time.time()
    settings = {"match_type": "lemma", "min_matches": 2, "language": LANGUAGE,
                 "stoplist_size": 10}
    matches, stoplist_size = matcher.find_matches(source_units, target_units, settings=settings)
    print(f"  Found {len(matches)} raw lemma matches in {time.time()-t0:.1f}s (stoplist={stoplist_size})")

    t0 = time.time()
    lemma_results = scorer.score_matches(matches, source_units, target_units,
                                         settings=settings)
    lemma_results.sort(key=lambda r: get_score(r), reverse=True)
    print(f"  Scored and sorted {len(lemma_results)} lemma results in {time.time()-t0:.1f}s")

    # Build fusion lookup: (source_ref, target_ref) -> (rank, score, info)
    fusion_lookup = {}
    for i, r in enumerate(fusion_results):
        key = get_ref(r)
        if key not in fusion_lookup:  # first occurrence = highest rank
            fusion_lookup[key] = (i + 1, get_score(r), r)

    # Analyze top N lemma results
    n_analyze = min(TOP_N, len(lemma_results))
    print(f"\n{'=' * 78}")
    print(f"TOP {n_analyze} LEMMA RESULTS — WHERE DO THEY LAND IN FUSION?")
    print(f"{'=' * 78}")

    found_in_fusion = 0
    not_in_fusion = 0
    fusion_ranks = []

    # Collect stats by fusion rank buckets
    buckets = {
        "1-15": 0, "16-50": 0, "51-100": 0, "101-200": 0,
        "201-500": 0, "501-1000": 0, "1001-5000": 0, "5000+": 0,
        "not found": 0
    }

    for i, lr in enumerate(lemma_results[:TOP_N]):
        lemma_rank = i + 1
        key = get_ref(lr)
        lemma_score = get_score(lr)
        matched_words = get_matched_words(lr)
        words_str = "+".join(matched_words[:5]) if matched_words else "?"
        n_words = len(matched_words)

        if key in fusion_lookup:
            frank, fscore, finfo = fusion_lookup[key]
            found_in_fusion += 1
            fusion_ranks.append(frank)

            # Bucket
            if frank <= 15: buckets["1-15"] += 1
            elif frank <= 50: buckets["16-50"] += 1
            elif frank <= 100: buckets["51-100"] += 1
            elif frank <= 200: buckets["101-200"] += 1
            elif frank <= 500: buckets["201-500"] += 1
            elif frank <= 1000: buckets["501-1000"] += 1
            elif frank <= 5000: buckets["1001-5000"] += 1
            else: buckets["5000+"] += 1

            # Print details for first 100 and any interesting cases
            flag = ""
            if frank > 10 * lemma_rank:
                flag = " *** BURIED"
            if frank <= 15 and lemma_rank > 50:
                flag = " *** PROMOTED"

            if lemma_rank <= 100 or frank > 500 or flag:
                # Get fusion channels
                f_channels = finfo.get("channels", [])
                f_n_channels = len(f_channels) if isinstance(f_channels, list) else finfo.get("n_channels", "?")

                print(f"  Lemma #{lemma_rank:4d} (score={lemma_score:.3f}, {n_words}w: {words_str:30s}) "
                      f"-> Fusion #{frank:5d} (score={fscore:.4f}, {f_n_channels}ch){flag}")
        else:
            not_in_fusion += 1
            buckets["not found"] += 1
            if lemma_rank <= 100:
                src_ref = lr.get("source", {}).get("ref", "?")
                tgt_ref = lr.get("target", {}).get("ref", "?")
                print(f"  Lemma #{lemma_rank:4d} (score={lemma_score:.3f}, {n_words}w: {words_str:30s}) "
                      f"-> NOT IN FUSION  [{src_ref} x {tgt_ref}]")

    # Summary
    print(f"\n{'=' * 78}")
    print(f"SUMMARY")
    print(f"{'=' * 78}")
    print(f"  Lemma results analyzed: {n_analyze}")
    print(f"  Found in fusion: {found_in_fusion}")
    print(f"  Not in fusion:   {not_in_fusion}")

    if fusion_ranks:
        import statistics
        print(f"\n  Fusion rank distribution for top {n_analyze} lemma results:")
        print(f"    Median fusion rank: {statistics.median(fusion_ranks):.0f}")
        print(f"    Mean fusion rank:   {statistics.mean(fusion_ranks):.0f}")
        print(f"    Min:  {min(fusion_ranks)}")
        print(f"    Max:  {max(fusion_ranks)}")
        if len(fusion_ranks) > 1:
            print(f"    Stdev: {statistics.stdev(fusion_ranks):.0f}")

    print(f"\n  Bucket distribution:")
    for bucket, count in buckets.items():
        pct = count / n_analyze * 100 if n_analyze > 0 else 0
        bar = "#" * int(pct / 2)
        print(f"    Fusion {bucket:>10s}: {count:4d} ({pct:5.1f}%) {bar}")

    # Show the biggest rank drops (lemma top 50 that are fusion 200+)
    print(f"\n  BIGGEST RANK DROPS (lemma top-50 -> fusion 200+):")
    drops = []
    for i, lr in enumerate(lemma_results[:50]):
        key = get_ref(lr)
        if key in fusion_lookup:
            frank, fscore, finfo = fusion_lookup[key]
            if frank > 200:
                matched_words = get_matched_words(lr)
                drops.append((i+1, frank, get_score(lr), fscore,
                              "+".join(matched_words[:5])))

    drops.sort(key=lambda x: x[1], reverse=True)
    for lemma_r, fusion_r, lscore, fscore, words in drops[:20]:
        print(f"    Lemma #{lemma_r} -> Fusion #{fusion_r}  "
              f"(lemma_score={lscore:.3f}, fusion_score={fscore:.4f})  {words}")

    if not drops:
        print("    (none)")


if __name__ == "__main__":
    main()
