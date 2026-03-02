#!/usr/bin/env python3
"""
Compare fusion search vs rare-pairs search on Aen.7 × Punica 2.

Runs both searches, expands rare-pair bigrams to line pairs, and shows
where each rare-pair hit lands in the fusion ranking.

Usage:
    TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/compare_fusion_vs_rarepairs.py
"""

import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.fusion import run_fusion_search
from backend.bigram_frequency import (
    is_bigram_cache_available, load_bigram_cache,
    extract_bigrams, get_bigram_rarity_score, make_bigram_key
)

TEXTS_DIR = PROJECT_ROOT / "texts"

SOURCE_FILE = os.environ.get("SOURCE_FILE", "vergil.aeneid.part.7.tess")
TARGET_FILE = os.environ.get("TARGET_FILE", "silius_italicus.punica.part.2.tess")
LANGUAGE = os.environ.get("LANGUAGE", "la")
MIN_RARITY = float(os.environ.get("MIN_RARITY", "0.9"))
RP_LIMIT = int(os.environ.get("RP_LIMIT", "500"))


def find_text_path(filename):
    for p in TEXTS_DIR.rglob(filename):
        return p
    return None


def get_ref(result):
    src = result.get("source", {})
    tgt = result.get("target", {})
    return (src.get("ref", ""), tgt.get("ref", ""))


def get_score(result):
    return result.get("overall_score", result.get("score", 0))


def extract_bigram_locations(units, language):
    """Build dict: bigram_key -> list of {ref, text, line_idx}."""
    locations = defaultdict(list)
    for idx, unit in enumerate(units):
        lemmas = unit.get('lemmas', [])
        ref = unit.get('ref', '')
        text = unit.get('text', '')
        # Extract bigrams from this line's lemmas
        seen = set()
        for i in range(len(lemmas)):
            for j in range(i + 1, len(lemmas)):
                l1, l2 = lemmas[i], lemmas[j]
                if not l1 or not l2 or len(l1) <= 2 or len(l2) <= 2:
                    continue
                key = make_bigram_key(l1, l2)
                if key and key not in seen:
                    seen.add(key)
                    locations[key].append({
                        'ref': ref,
                        'text': text,
                        'line_idx': idx
                    })
    return locations


def run_rare_pairs(source_units, target_units, language, min_rarity):
    """Replicate the rare-bigram-search logic."""
    print(f"\n--- Running rare pairs search (min_rarity={min_rarity}) ---")

    if not is_bigram_cache_available(language):
        print("  ERROR: Bigram cache not available!")
        return []

    load_bigram_cache(language)

    t0 = time.time()
    source_locs = extract_bigram_locations(source_units, language)
    target_locs = extract_bigram_locations(target_units, language)
    print(f"  Source unique bigrams: {len(source_locs)}")
    print(f"  Target unique bigrams: {len(target_locs)}")

    shared = set(source_locs.keys()) & set(target_locs.keys())
    print(f"  Shared bigrams: {len(shared)}")

    results = []
    for bg_key in shared:
        rarity = get_bigram_rarity_score(bg_key, language)
        if rarity >= min_rarity:
            words = bg_key.split('|')
            lemma1 = words[0] if len(words) > 0 else ''
            lemma2 = words[1] if len(words) > 1 else ''
            results.append({
                'bigram_key': bg_key,
                'lemma1': lemma1,
                'lemma2': lemma2,
                'rarity': rarity,
                'source_locs': source_locs[bg_key],
                'target_locs': target_locs[bg_key],
            })

    results.sort(key=lambda x: -x['rarity'])
    elapsed = time.time() - t0
    print(f"  Rare bigrams (rarity >= {min_rarity}): {len(results)} in {elapsed:.1f}s")
    return results


def normalize_ref(ref_str):
    """Normalize a ref to (book, line) for flexible matching."""
    nums = [int(x) for x in re.findall(r'\d+', str(ref_str))]
    if len(nums) >= 2:
        return nums[-2], nums[-1]
    if len(nums) == 1:
        return 1, nums[0]
    return None, None


def main():
    print("=" * 78)
    print("FUSION vs RARE PAIRS COMPARISON")
    print(f"Source: {SOURCE_FILE}")
    print(f"Target: {TARGET_FILE}")
    print(f"Min rarity: {MIN_RARITY}")
    print("=" * 78)

    src_path = find_text_path(SOURCE_FILE)
    tgt_path = find_text_path(TARGET_FILE)
    if not src_path or not tgt_path:
        print("ERROR: Could not find text files")
        return

    print("\nInitializing components...")
    tp = TextProcessor()
    matcher = Matcher()
    scorer = Scorer()

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
    print(f"  Fusion: {len(fusion_results)} results in {time.time()-t0:.1f}s")

    # Build fusion lookup: (source_ref, target_ref) -> (rank, score, result)
    fusion_lookup = {}
    for i, r in enumerate(fusion_results):
        key = get_ref(r)
        if key not in fusion_lookup:
            fusion_lookup[key] = (i + 1, get_score(r), r)

    # Also build a (book, line) lookup for flexible matching
    fusion_bl_lookup = {}
    for i, r in enumerate(fusion_results):
        src_ref = r.get("source", {}).get("ref", "")
        tgt_ref = r.get("target", {}).get("ref", "")
        sb, sl = normalize_ref(src_ref)
        tb, tl = normalize_ref(tgt_ref)
        if sb is not None and tb is not None:
            bl_key = (sb, sl, tb, tl)
            if bl_key not in fusion_bl_lookup:
                fusion_bl_lookup[bl_key] = (i + 1, get_score(r), r)

    # 2) Run rare pairs search
    rp_results = run_rare_pairs(source_units, target_units, LANGUAGE, MIN_RARITY)

    if not rp_results:
        print("\nNo rare pair results found. Try lowering MIN_RARITY.")
        return

    # 3) Expand rare pairs to line pairs and find fusion ranks
    print(f"\n{'=' * 78}")
    print(f"RARE PAIR RESULTS — WHERE DO THEY LAND IN FUSION?")
    print(f"{'=' * 78}")

    # For each rare bigram, show all source×target pairs
    total_pairs = 0
    pairs_in_top15 = 0
    pairs_in_top50 = 0
    pairs_in_top100 = 0
    pairs_in_top500 = 0
    pairs_in_top1000 = 0
    pairs_buried = 0  # > 5000

    bigram_summary = []

    for rp in rp_results[:RP_LIMIT]:
        bigram_label = f"{rp['lemma1']}+{rp['lemma2']}"
        rarity = rp['rarity']

        # All source×target line pairs for this bigram
        best_fusion_rank = float('inf')
        pair_details = []

        for sloc in rp['source_locs']:
            for tloc in rp['target_locs']:
                total_pairs += 1
                src_ref = sloc['ref']
                tgt_ref = tloc['ref']

                # Try exact ref match first
                key = (src_ref, tgt_ref)
                found = fusion_lookup.get(key)

                # Fall back to book/line match
                if not found:
                    sb, sl = normalize_ref(src_ref)
                    tb, tl = normalize_ref(tgt_ref)
                    if sb is not None and tb is not None:
                        found = fusion_bl_lookup.get((sb, sl, tb, tl))

                if found:
                    frank, fscore, finfo = found
                    if frank < best_fusion_rank:
                        best_fusion_rank = frank
                    pair_details.append((src_ref, tgt_ref, frank, fscore))

                    if frank <= 15: pairs_in_top15 += 1
                    if frank <= 50: pairs_in_top50 += 1
                    if frank <= 100: pairs_in_top100 += 1
                    if frank <= 500: pairs_in_top500 += 1
                    if frank <= 1000: pairs_in_top1000 += 1
                    if frank > 5000: pairs_buried += 1
                else:
                    pair_details.append((src_ref, tgt_ref, None, None))

        bigram_summary.append({
            'label': bigram_label,
            'rarity': rarity,
            'n_src': len(rp['source_locs']),
            'n_tgt': len(rp['target_locs']),
            'n_pairs': len(pair_details),
            'best_fusion_rank': best_fusion_rank if best_fusion_rank < float('inf') else None,
            'pairs': pair_details,
        })

    # Print each rare bigram with its best fusion rank
    print(f"\n{'Rarity':>7s}  {'Bigram':<30s}  {'Src×Tgt':>7s}  {'Best Fusion Rank':>16s}  Details")
    print("-" * 100)
    for bs in bigram_summary:
        best_str = f"#{bs['best_fusion_rank']}" if bs['best_fusion_rank'] else "NOT FOUND"
        flag = ""
        if bs['best_fusion_rank'] and bs['best_fusion_rank'] <= 15:
            flag = " *** TOP-15"
        elif bs['best_fusion_rank'] and bs['best_fusion_rank'] > 5000:
            flag = " *** BURIED"

        print(f"  {bs['rarity']:.4f}  {bs['label']:<30s}  {bs['n_src']}×{bs['n_tgt']:>3d}  {best_str:>16s}{flag}")

        # Show individual pairs for this bigram (first 5)
        for src_ref, tgt_ref, frank, fscore in bs['pairs'][:5]:
            if frank:
                print(f"           {src_ref} × {tgt_ref} -> Fusion #{frank} (score={fscore:.4f})")
            else:
                print(f"           {src_ref} × {tgt_ref} -> NOT IN FUSION")
        if len(bs['pairs']) > 5:
            print(f"           ... and {len(bs['pairs'])-5} more pairs")

    # Summary
    print(f"\n{'=' * 78}")
    print(f"SUMMARY")
    print(f"{'=' * 78}")
    print(f"  Rare bigrams found: {len(bigram_summary)}")
    print(f"  Total line pairs:   {total_pairs}")
    print(f"")
    print(f"  Line pairs in fusion top 15:    {pairs_in_top15}")
    print(f"  Line pairs in fusion top 50:    {pairs_in_top50}")
    print(f"  Line pairs in fusion top 100:   {pairs_in_top100}")
    print(f"  Line pairs in fusion top 500:   {pairs_in_top500}")
    print(f"  Line pairs in fusion top 1000:  {pairs_in_top1000}")
    print(f"  Line pairs buried (>5000):      {pairs_buried}")
    print(f"")

    # Count how many BIGRAMS have at least one pair in fusion top N
    bg_top15 = sum(1 for b in bigram_summary if b['best_fusion_rank'] and b['best_fusion_rank'] <= 15)
    bg_top50 = sum(1 for b in bigram_summary if b['best_fusion_rank'] and b['best_fusion_rank'] <= 50)
    bg_top100 = sum(1 for b in bigram_summary if b['best_fusion_rank'] and b['best_fusion_rank'] <= 100)
    bg_top500 = sum(1 for b in bigram_summary if b['best_fusion_rank'] and b['best_fusion_rank'] <= 500)
    bg_top1000 = sum(1 for b in bigram_summary if b['best_fusion_rank'] and b['best_fusion_rank'] <= 1000)
    bg_buried = sum(1 for b in bigram_summary if b['best_fusion_rank'] and b['best_fusion_rank'] > 5000)
    bg_notfound = sum(1 for b in bigram_summary if b['best_fusion_rank'] is None)

    print(f"  Bigrams with best pair in fusion top 15:   {bg_top15}/{len(bigram_summary)}")
    print(f"  Bigrams with best pair in fusion top 50:   {bg_top50}/{len(bigram_summary)}")
    print(f"  Bigrams with best pair in fusion top 100:  {bg_top100}/{len(bigram_summary)}")
    print(f"  Bigrams with best pair in fusion top 500:  {bg_top500}/{len(bigram_summary)}")
    print(f"  Bigrams with best pair in fusion top 1000: {bg_top1000}/{len(bigram_summary)}")
    print(f"  Bigrams buried (best pair > 5000):         {bg_buried}/{len(bigram_summary)}")
    print(f"  Bigrams not found in fusion:               {bg_notfound}/{len(bigram_summary)}")


if __name__ == "__main__":
    main()
