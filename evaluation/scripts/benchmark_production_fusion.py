#!/usr/bin/env python3
"""
Benchmark the production fusion search (backend/fusion.py) against gold standards.

Compares production fusion (selective window channels, per-channel caps,
boost isolation) to the Phase 2 evaluation results (all channels on windows).

Usage:
    TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/benchmark_production_fusion.py
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.fusion import run_fusion_search

TEXTS_DIR = PROJECT_ROOT / "texts"
BENCHMARKS_DIR = PROJECT_ROOT / "evaluation" / "benchmarks"

# Benchmark definitions: (display_name, source_file, target_file, benchmark_key)
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
    """Parse a ref that might be a range (e.g., 'luc. 1.1-luc. 1.2')."""
    if '-' in ref_str:
        # Range ref from window
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


def evaluate_results(results, gold_entries, k_values=[10, 50, 100, 500]):
    """Evaluate recall and P@K against gold standard."""
    # Pre-parse gold entries
    parsed_gold = []
    for i, g in enumerate(gold_entries):
        gs_b, gs_l = parse_ref(g["source_ref"])
        gt_b, gt_l = parse_ref(g["target_ref"])
        if gs_b is not None and gt_b is not None:
            parsed_gold.append((i, gs_b, gs_l, gt_b, gt_l))

    gold_found = set()
    recall_at_k = {}
    precision_at_k = {}

    for rank, result in enumerate(results, 1):
        source_ref = result.get("source", {}).get("ref", "") if isinstance(result.get("source"), dict) else result.get("source_ref", "")
        target_ref = result.get("target", {}).get("ref", "") if isinstance(result.get("target"), dict) else result.get("target_ref", "")

        # Handle both line refs and window range refs
        rs_b1, rs_l1, rs_b2, rs_l2 = parse_range_ref(source_ref)
        rt_b1, rt_l1, rt_b2, rt_l2 = parse_range_ref(target_ref)

        if rs_b1 is not None and rt_b1 is not None:
            for gi, gs_b, gs_l, gt_b, gt_l in parsed_gold:
                if gi in gold_found:
                    continue
                # Source: gold line must fall within the result's source range
                source_match = (gs_b == rs_b1 and rs_l1 <= gs_l <= rs_l2)
                # Target: gold line must be within ±3 of result's target range
                target_match = (gt_b == rt_b1 and
                               rt_l1 - 3 <= gt_l <= rt_l2 + 3)
                if source_match and target_match:
                    gold_found.add(gi)

        if rank in k_values:
            recall_at_k[rank] = len(gold_found)
            precision_at_k[rank] = len(gold_found) / rank

    # Final recall (all results)
    total_found = len(gold_found)
    total_gold = len(parsed_gold)

    return {
        "total_found": total_found,
        "total_gold": total_gold,
        "recall": total_found / total_gold if total_gold > 0 else 0,
        "recall_at_k": recall_at_k,
        "precision_at_k": precision_at_k,
        "total_results": len(results),
    }


def main():
    print("=" * 80)
    print("PRODUCTION FUSION BENCHMARK")
    print("Testing backend/fusion.py against gold standards")
    print("=" * 80)
    print()

    # Initialize components
    print("Initializing TextProcessor, Matcher, Scorer...")
    tp = TextProcessor()
    matcher = Matcher()
    scorer = Scorer()

    # Phase 2 comparison numbers (from EVALUATION_REPORT.md)
    phase2_recall = {
        "lucan_vergil": (192, 213, 0.9014),
        "vf_vergil": (472, 521, 0.9060),
        "achilleid_vergil": (48, 53, 0.9057),
        "achilleid_ovid": (23, 23, 1.0000),
        "achilleid_thebaid": (48, 52, 0.9231),
    }
    phase2_p10 = {
        "lucan_vergil": 0.50,
        "vf_vergil": 0.90,
        "achilleid_vergil": 0.00,
        "achilleid_ovid": 0.10,
        "achilleid_thebaid": 0.00,
    }

    all_results_data = []

    for display_name, source_file, target_file, bench_key in BENCHMARKS:
        print(f"\n{'='*70}")
        print(f"  {display_name}")
        print(f"{'='*70}")

        # Load gold
        gold_entries = load_gold(bench_key)
        if gold_entries is None:
            print(f"  ERROR: Could not load gold for {bench_key}")
            continue
        print(f"  Gold entries: {len(gold_entries)}")

        # Load text units
        source_path = TEXTS_DIR / "la" / source_file
        target_path = TEXTS_DIR / "la" / target_file

        if not source_path.exists():
            print(f"  ERROR: Source file not found: {source_path}")
            continue
        if not target_path.exists():
            print(f"  ERROR: Target file not found: {target_path}")
            continue

        print(f"  Processing source: {source_file}")
        source_units = tp.process_file(str(source_path), "la", "line")
        print(f"  -> {len(source_units)} source units")

        print(f"  Processing target: {target_file}")
        target_units = tp.process_file(str(target_path), "la", "line")
        print(f"  -> {len(target_units)} target units")

        # Run production fusion search with high max_results
        print(f"\n  Running production fusion search (mode=merged, max_results=0)...")
        t0 = time.time()

        def progress(step, total, ch_name, phase):
            elapsed = time.time() - t0
            print(f"    [{phase}] Channel {step}/{total}: {ch_name} ({elapsed:.1f}s)")

        results = run_fusion_search(
            source_units, target_units,
            matcher, scorer,
            source_file, target_file,
            language='la',
            mode='merged',
            max_results=0,  # Return all results
            source_path=str(source_path),
            target_path=str(target_path),
            progress_callback=progress,
        )

        elapsed = time.time() - t0
        print(f"\n  Fusion complete: {len(results)} results in {elapsed:.1f}s")

        if results:
            scores = [r.get("fused_score", 0) for r in results]
            print(f"  Score range: {max(scores):.2f} - {min(scores):.2f}")
            channels = [r.get("channel_count", 0) for r in results]
            print(f"  Channel count range: {max(channels)} - {min(channels)}")

        # Evaluate
        eval_result = evaluate_results(results, gold_entries, k_values=[10, 50, 100, 500, 1000, 5000])

        # Print results
        print(f"\n  RECALL: {eval_result['total_found']}/{eval_result['total_gold']} = {eval_result['recall']:.1%}")

        # Comparison with Phase 2
        p2_found, p2_gold, p2_recall = phase2_recall.get(bench_key, (0, 0, 0))
        diff = eval_result['total_found'] - p2_found
        diff_str = f"+{diff}" if diff >= 0 else str(diff)
        print(f"  Phase 2:     {p2_found}/{p2_gold} = {p2_recall:.1%}")
        print(f"  Production:  {eval_result['total_found']}/{eval_result['total_gold']} = {eval_result['recall']:.1%}  ({diff_str})")

        print(f"\n  P@K:")
        for k in sorted(eval_result['precision_at_k'].keys()):
            p_at_k = eval_result['precision_at_k'][k]
            r_at_k = eval_result['recall_at_k'][k] / eval_result['total_gold'] if eval_result['total_gold'] > 0 else 0
            p2_p10_val = phase2_p10.get(bench_key, "?")
            marker = ""
            if k == 10:
                marker = f"  (Phase 2 P@10: {p2_p10_val:.0%})"
            print(f"    P@{k:>4}: {p_at_k:.1%}   R@{k:>4}: {r_at_k:.1%}{marker}")

        all_results_data.append({
            "name": display_name,
            "key": bench_key,
            "eval": eval_result,
            "elapsed": elapsed,
        })

    # Summary table
    print(f"\n\n{'='*80}")
    print("SUMMARY: Production Fusion vs Phase 2 Evaluation")
    print(f"{'='*80}\n")

    header = f"{'Benchmark':<30} {'Phase 2':>12} {'Production':>12} {'Diff':>6} {'P@10':>6} {'Time':>8}"
    print(header)
    print("-" * len(header))

    total_prod_found = 0
    total_p2_found = 0
    total_gold = 0

    for r in all_results_data:
        p2_found, p2_gold, p2_recall = phase2_recall.get(r["key"], (0, 0, 0))
        prod_found = r["eval"]["total_found"]
        prod_gold = r["eval"]["total_gold"]
        diff = prod_found - p2_found
        diff_str = f"+{diff}" if diff >= 0 else str(diff)
        p10 = r["eval"]["precision_at_k"].get(10, 0)
        elapsed = r["elapsed"]

        total_prod_found += prod_found
        total_p2_found += p2_found
        total_gold += prod_gold

        print(f"{r['name']:<30} {p2_found:>4}/{p2_gold:<4} {p2_recall:>5.1%} "
              f"{prod_found:>4}/{prod_gold:<4} {prod_found/prod_gold:>5.1%} "
              f"{diff_str:>6} {p10:>5.0%} {elapsed:>7.0f}s")

    total_diff = total_prod_found - total_p2_found
    diff_str = f"+{total_diff}" if total_diff >= 0 else str(total_diff)
    print("-" * len(header))
    print(f"{'TOTAL':<30} {total_p2_found:>4}/{total_gold:<4} {total_p2_found/total_gold:>5.1%} "
          f"{total_prod_found:>4}/{total_gold:<4} {total_prod_found/total_gold:>5.1%} "
          f"{diff_str:>6}")

    print(f"\n\nKey differences from Phase 2 evaluation:")
    print(f"  - Window pass: 4 channels (lemma, lemma_min1, rare_word, dictionary) vs all 9 in Phase 2")
    print(f"  - Syntax channel: restored (uses syntax_latin.db with lemma-inverted-index pruning)")
    print(f"  - Scorer boosts: explicitly disabled in fusion mode")
    print(f"  - Per-channel caps: 50K for lemma_min1/semantic/sound/edit_distance")
    print()


if __name__ == "__main__":
    main()
