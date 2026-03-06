#!/usr/bin/env python3
"""
Test syntax gate thresholds against 5 gold benchmarks.

Runs the benchmark suite twice:
  1. Syntax ON  (current production config)
  2. Syntax OFF (simulates a pair-size gate that excludes all benchmarks)

Since all 5 benchmarks have comparison space < 15M while the problematic
large pairs (e.g., Aeneid × Met = 119M) are far above, any threshold
between 15M and 119M gives identical benchmark results. This test
measures the recall cost of disabling syntax entirely, which is the
worst case for any threshold.

Usage:
    TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/test_syntax_gate.py
"""

import json
import os
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.fusion import run_fusion_search, CHANNEL_CONFIGS

TEXTS_DIR = PROJECT_ROOT / "texts"
BENCHMARKS_DIR = PROJECT_ROOT / "evaluation" / "benchmarks"

BENCHMARKS = [
    ("Lucan-Vergil",
     "lucan.bellum_civile.part.1.tess", "vergil.aeneid.tess",
     "lucan_vergil"),
    ("VF-Vergil",
     "valerius_flaccus.argonautica.part.1.tess", "vergil.aeneid.tess",
     "vf_vergil"),
    ("Achilleid-Vergil",
     "statius.achilleid.tess", "vergil.aeneid.tess",
     "achilleid_vergil"),
    ("Achilleid-Ovid",
     "statius.achilleid.tess", "ovid.metamorphoses.tess",
     "achilleid_ovid"),
    ("Achilleid-Thebaid",
     "statius.achilleid.tess", "statius.thebaid.tess",
     "achilleid_thebaid"),
]


def load_gold(benchmark_key):
    if benchmark_key == "lucan_vergil":
        return json.load(open(BENCHMARKS_DIR / "lucan_vergil_lexical_benchmark.json"))
    elif benchmark_key == "vf_vergil":
        return json.load(open(BENCHMARKS_DIR / "vf_vergil_gold.json"))
    elif benchmark_key.startswith("achilleid_"):
        data = json.load(open(BENCHMARKS_DIR / "achilleid_gold_2plus_commentators.json"))
        target_map = {
            "achilleid_vergil": "vergil.aeneid.tess",
            "achilleid_ovid": "ovid.metamorphoses.tess",
            "achilleid_thebaid": "statius.thebaid.tess",
        }
        target = target_map.get(benchmark_key)
        return [e for e in data if e.get("target_work") == target] if target else None
    return None


def parse_ref(ref_str):
    nums = [int(x) for x in re.findall(r'\d+', str(ref_str))]
    if len(nums) >= 2:
        return nums[-2], nums[-1]
    if len(nums) == 1:
        return 1, nums[0]
    return None, None


def parse_range_ref(ref_str):
    if '-' in ref_str:
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


def count_gold_found(results, gold_entries):
    parsed_gold = []
    for i, g in enumerate(gold_entries):
        gs_b, gs_l = parse_ref(g["source_ref"])
        gt_b, gt_l = parse_ref(g["target_ref"])
        if gs_b is not None and gt_b is not None:
            parsed_gold.append((i, gs_b, gs_l, gt_b, gt_l))

    gold_found = set()
    for result in results:
        source_ref = result.get("source", {}).get("ref", "")
        target_ref = result.get("target", {}).get("ref", "")
        rs_b1, rs_l1, rs_b2, rs_l2 = parse_range_ref(source_ref)
        rt_b1, rt_l1, rt_b2, rt_l2 = parse_range_ref(target_ref)

        if rs_b1 is not None and rt_b1 is not None:
            for gi, gs_b, gs_l, gt_b, gt_l in parsed_gold:
                if gi in gold_found:
                    continue
                source_match = (gs_b == rs_b1 and rs_l1 <= gs_l <= rs_l2)
                target_match = (gt_b == rt_b1 and rt_l1 - 3 <= gt_l <= rt_l2 + 3)
                if source_match and target_match:
                    gold_found.add(gi)

    return len(gold_found), len(parsed_gold)


def main():
    print("=" * 70)
    print("SYNTAX GATE THRESHOLD TEST")
    print("=" * 70)

    tp = TextProcessor()
    matcher = Matcher()
    scorer = Scorer()

    # Store original syntax config
    original_syntax_config = dict(CHANNEL_CONFIGS.get("syntax", {}))

    # Pre-load all text units (reused across both configs)
    text_cache = {}
    for _, src, tgt, _ in BENCHMARKS:
        for f in [src, tgt]:
            if f not in text_cache:
                path = TEXTS_DIR / "la" / f
                text_cache[f] = tp.process_file(str(path), "la", "line")

    configs_to_test = [
        ("Syntax ON", True),
        ("Syntax OFF", False),
    ]

    all_results = {}

    for config_label, syntax_enabled in configs_to_test:
        print(f"\n{'='*70}")
        print(f"  Configuration: {config_label}")
        print(f"{'='*70}")

        if not syntax_enabled:
            # Disable syntax by removing it from CHANNEL_CONFIGS temporarily
            if "syntax" in CHANNEL_CONFIGS:
                del CHANNEL_CONFIGS["syntax"]
        else:
            # Ensure syntax is enabled
            CHANNEL_CONFIGS["syntax"] = original_syntax_config

        config_results = {}
        total_found = 0
        total_gold = 0

        for label, src, tgt, key in BENCHMARKS:
            gold = load_gold(key)
            source_units = text_cache[src]
            target_units = text_cache[tgt]
            space = len(source_units) * len(target_units)

            print(f"\n  {label} ({len(source_units)} x {len(target_units)} = {space:,})")

            t0 = time.time()
            results = run_fusion_search(
                source_units, target_units,
                matcher, scorer, src, tgt,
                language='la', mode='merged', max_results=0,
                source_path=str(TEXTS_DIR / "la" / src),
                target_path=str(TEXTS_DIR / "la" / tgt),
            )
            elapsed = time.time() - t0

            found, gold_total = count_gold_found(results, gold)
            pct = found / gold_total * 100 if gold_total > 0 else 0
            total_found += found
            total_gold += gold_total
            config_results[key] = (found, gold_total, elapsed)

            print(f"    {found}/{gold_total} ({pct:.1f}%) in {elapsed:.0f}s")

        all_results[config_label] = (config_results, total_found, total_gold)
        pct = total_found / total_gold * 100 if total_gold > 0 else 0
        print(f"\n  TOTAL: {total_found}/{total_gold} ({pct:.1f}%)")

    # Restore syntax config
    CHANNEL_CONFIGS["syntax"] = original_syntax_config

    # Comparison table
    print(f"\n\n{'='*70}")
    print("COMPARISON: Syntax ON vs Syntax OFF")
    print(f"{'='*70}\n")

    header = f"{'Benchmark':<25} {'Syntax ON':>12} {'Syntax OFF':>12} {'Diff':>6} {'ON time':>8} {'OFF time':>8}"
    print(header)
    print("-" * len(header))

    on_results, on_total, on_gold = all_results["Syntax ON"]
    off_results, off_total, off_gold = all_results["Syntax OFF"]

    for label, _, _, key in BENCHMARKS:
        on_f, on_g, on_t = on_results[key]
        off_f, off_g, off_t = off_results[key]
        diff = on_f - off_f
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"{label:<25} {on_f:>4}/{on_g:<4} {on_f/on_g*100:>5.1f}%"
              f" {off_f:>4}/{off_g:<4} {off_f/off_g*100:>5.1f}%"
              f" {diff_str:>6}"
              f" {on_t:>7.0f}s {off_t:>7.0f}s")

    diff_total = on_total - off_total
    diff_str = f"+{diff_total}" if diff_total > 0 else str(diff_total)
    print("-" * len(header))
    print(f"{'TOTAL':<25} {on_total:>4}/{on_gold:<4} {on_total/on_gold*100:>5.1f}%"
          f" {off_total:>4}/{off_gold:<4} {off_total/off_gold*100:>5.1f}%"
          f" {diff_str:>6}")

    print(f"\n\nThreshold recommendations:")
    print(f"  Benchmark max comparison space: 13,495,500 (Achilleid-Ovid)")
    print(f"  Aeneid x Met comparison space:  118,712,416")
    print(f"  Any threshold between 15M and 118M gives identical benchmark recall.")
    print(f"  Recommended: 50,000,000 (50M) — conservative, well above all benchmarks.")
    print()


if __name__ == "__main__":
    main()
