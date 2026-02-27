#!/usr/bin/env python3
"""
Fusion Weight Optimization — Grid Search over Channel Weights

Exploits the key insight that channel results are independent of fusion
parameters: we run all 9 channels ONCE per benchmark (~10 min total),
then re-fuse with thousands of weight/bonus/penalty configurations
(milliseconds each) to find optimal settings.

Key optimizations over the naive approach:
  1. Extract lightweight pair summaries (just refs, raw scores, stopword flags,
     gold matches) and discard heavy result dicts — reduces memory from ~7GB
     to ~100MB
  2. Use numpy for vectorized score computation — matrix multiply instead of
     Python loops
  3. Skip windows in the sweep — windows are appended AFTER all line results,
     so they never affect recall@500 (there are always >100K line pairs)
  4. Total recall is constant across configs (same pair set, different order),
     so the 90% guard is checked once

Two-phase sweep:
  Phase 2a: Sweep all 34,992 weight configs with current bonus/penalty
  Phase 2b: Sweep convergence_bonus × stopword_penalty with best weights

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
    CONVERGENCE_BONUS, FUNCTION_WORD_PENALTY,
    WINDOW_CHANNELS,
    run_channel, fuse_results, merge_line_and_window, make_window_units,
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
STOPWORD_PENALTY_GRID = [0.1, 0.2, 0.3, 0.5, 1.0]


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

def extract_pair_summary(channel_results, parsed_gold, stop_words):
    """Extract lightweight pair summaries from channel results.

    Aggregates per-channel results into per-pair data:
    - Raw score per channel (9-element vector for weighted sum)
    - Channel count (for convergence bonus)
    - Stopword-only flag (for penalty)
    - Gold match indices (for recall evaluation)

    Returns numpy arrays for vectorized computation in the sweep.
    """
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

            # Accumulate matched words for stopword detection
            for mw in r.get("matched_words", []):
                lemma = mw.get("lemma", "")
                if lemma and lemma not in pair_data[key]["matched_words"]:
                    pair_data[key]["matched_words"][lemma] = mw

    # Step 2: Build numpy arrays
    N = len(pair_data)
    C = len(CHANNEL_NAMES)

    scores_matrix = np.zeros((N, C), dtype=np.float64)
    n_channels = np.zeros(N, dtype=np.float64)
    is_stopword = np.zeros(N, dtype=bool)
    gold_matches = []

    for i, ((src_ref, tgt_ref), data) in enumerate(pair_data.items()):
        scores_matrix[i] = data["scores"]
        n_channels[i] = data["n_ch"]

        # Stopword check (same logic as _compute_rarity_multiplier)
        mw = data["matched_words"]
        has_content = False
        has_any_idf = False
        for lemma, info in mw.items():
            idf = info.get('idf', 0)
            if idf <= 0:
                continue
            has_any_idf = True
            if lemma not in stop_words:
                has_content = True
                break
        is_stopword[i] = has_any_idf and not has_content

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
        "is_stopword": is_stopword,
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


def evaluate_config_fast(summaries, weight_vector, bonus, penalty,
                         k_values=(100, 500)):
    """Evaluate a single config across all benchmarks.

    Uses numpy vectorized operations:
      fused = scores_matrix @ weight_vector + bonus * (n_channels - 1)
      fused[is_stopword] *= penalty
      top_k = argpartition + argsort (O(N) + O(K log K))

    Returns dict with recall@K metrics.
    """
    total_gold = 0
    found_at_k = defaultdict(int)
    max_k = max(k_values)
    k_set = set(k_values)

    for bench_key, s in summaries.items():
        sm = s["scores_matrix"]
        nc = s["n_channels"]
        sw = s["is_stopword"]
        gm = s["gold_matches"]
        n_gold = s["n_gold"]
        total_gold += n_gold
        N = s["n_pairs"]

        # Vectorized score computation
        fused = sm @ weight_vector + bonus * (nc - 1.0)
        if penalty != 1.0:
            fused[sw] *= penalty

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


def run_weight_sweep(summaries, convergence_bonus, stopword_penalty):
    """Phase 2a: Sweep all weight configs with fixed bonus/penalty."""
    weight_configs = generate_weight_configs()
    total = len(weight_configs)
    log(f"\nPhase 2a: Sweeping {total:,} weight configurations...")
    log(f"  Fixed: convergence_bonus={convergence_bonus}, "
        f"stopword_penalty={stopword_penalty}")

    results = []
    t0 = time.time()
    last_report = t0

    for i, weights in enumerate(weight_configs):
        wv = weights_to_vector(weights)
        metrics = evaluate_config_fast(
            summaries, wv, convergence_bonus, stopword_penalty,
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


def run_bonus_penalty_sweep(summaries, best_weights):
    """Phase 2b: Sweep convergence_bonus × stopword_penalty with best weights."""
    combos = list(itertools.product(CONVERGENCE_GRID, STOPWORD_PENALTY_GRID))
    total = len(combos)
    log(f"\nPhase 2b: Sweeping {total} bonus × penalty configs...")

    wv = weights_to_vector(best_weights)
    results = []
    for bonus, penalty in combos:
        metrics = evaluate_config_fast(
            summaries, wv, bonus, penalty,
            k_values=(100, 500),
        )
        results.append((bonus, penalty, metrics))

    results.sort(key=lambda x: _objective(x[2]), reverse=True)
    log(f"  Bonus/penalty sweep complete: {total} configs")
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


def print_top_configs(weight_results, bonus_penalty_results, summaries,
                      total_recall_info,
                      current_weights, current_bonus, current_penalty):
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
        summaries, wv_current, current_bonus, current_penalty,
        k_values=(10, 50, 100, 500, 1000, 5000),
    )
    log(f"\n--- Current Config D (baseline) ---")
    log(f"  Weights: {format_weights(current_weights)}")
    log(f"  Bonus: {current_bonus}, Penalty: {current_penalty}")
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

    log(f"\n  Changes from Config D:")
    any_change = False
    for k in CHANNEL_NAMES:
        if best_weights[k] != current_weights[k]:
            log(f"    {k}: {current_weights[k]} -> {best_weights[k]}")
            any_change = True
    if not any_change:
        log(f"    (no changes — current weights are optimal)")

    # Top bonus/penalty configs (Phase 2b)
    if bonus_penalty_results:
        log(f"\n--- Top 10 Bonus x Penalty Configs (Phase 2b) ---")
        log(f"{'Rank':>4} {'Bonus':>7} {'Penalty':>8} {'R@500':>8} "
            f"{'R@100':>8} {'F@500':>6} {'F@100':>6}")
        log("-" * 65)

        for rank, (bonus, penalty, metrics) in enumerate(
                bonus_penalty_results[:10], 1):
            r500 = metrics.get("recall_at_500", 0)
            r100 = metrics.get("recall_at_100", 0)
            f500 = metrics.get("found_at_500", 0)
            f100 = metrics.get("found_at_100", 0)
            is_current = (bonus == current_bonus and penalty == current_penalty)
            marker = " <-- CURRENT" if is_current else ""
            log(f"{rank:>4} {bonus:>7.2f} {penalty:>8.2f} {r500:>7.1%} "
                f"{r100:>7.1%}  {f500:>5} {f100:>5}{marker}")

    # Final recommendation
    if bonus_penalty_results:
        best_bonus, best_penalty, best_bp_metrics = bonus_penalty_results[0]
    else:
        best_bonus, best_penalty = current_bonus, current_penalty

    log(f"\n--- RECOMMENDATION ---")
    log(f"  Weights: {format_weights(best_weights)}")
    log(f"  Convergence bonus: {best_bonus}")
    log(f"  Stopword penalty: {best_penalty}")

    # Full evaluation of recommended config
    wv_best = weights_to_vector(best_weights)
    final_metrics = evaluate_config_fast(
        summaries, wv_best, best_bonus, best_penalty,
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
    log(f"\n  Improvement over Config D:")
    log(f"    R@500: {curr_r500:.1%} -> {rec_r500:.1%} "
        f"({rec_r500 - curr_r500:+.1%})")
    log(f"    R@100: {curr_r100:.1%} -> {rec_r100:.1%} "
        f"({rec_r100 - curr_r100:+.1%})")


def save_csv(weight_results, bonus_penalty_results, output_dir):
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

    if bonus_penalty_results:
        csv_path2 = output_dir / "bonus_penalty_sweep_results.csv"
        with open(csv_path2, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "rank", "convergence_bonus", "stopword_penalty",
                "recall_at_500", "recall_at_100",
                "found_at_500", "found_at_100", "total_gold",
            ])
            for rank, (bonus, penalty, metrics) in enumerate(
                    bonus_penalty_results, 1):
                writer.writerow([
                    rank, bonus, penalty,
                    f"{metrics.get('recall_at_500', 0):.4f}",
                    f"{metrics.get('recall_at_100', 0):.4f}",
                    metrics.get("found_at_500", 0),
                    metrics.get("found_at_100", 0),
                    metrics.get("total_gold", 0),
                ])
        log(f"  Bonus/penalty CSV: {csv_path2}")
        log(f"    ({len(bonus_penalty_results)} rows)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    t_start = time.time()

    log("=" * 80)
    log("FUSION WEIGHT OPTIMIZATION (v2 — numpy-accelerated)")
    log("Grid search over channel weights, convergence bonus, stopword penalty")
    log("=" * 80)

    weight_configs = generate_weight_configs()
    bp_combos = len(CONVERGENCE_GRID) * len(STOPWORD_PENALTY_GRID)
    log(f"\nSearch space:")
    log(f"  Weight configs: {len(weight_configs):,}")
    log(f"  Bonus x penalty: {bp_combos}")
    log(f"  Total (two-phase): {len(weight_configs):,} + {bp_combos}")
    log(f"\nCurrent Config D:")
    log(f"  {format_weights(CHANNEL_WEIGHTS)}")
    log(f"  convergence_bonus={CONVERGENCE_BONUS}, "
        f"stopword_penalty={FUNCTION_WORD_PENALTY}")

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
        s["scores_matrix"].nbytes + s["n_channels"].nbytes + s["is_stopword"].nbytes
        for s in summaries.values()
    ) / 1e6
    log(f"  Summary memory (arrays): {mem_mb:.1f} MB")

    # Phase 2a: Weight sweep
    log(f"\n{'='*80}")
    log("PHASE 2a: Weight grid sweep (numpy-accelerated)")
    log(f"{'='*80}")
    weight_results = run_weight_sweep(
        summaries, CONVERGENCE_BONUS, FUNCTION_WORD_PENALTY
    )

    # Phase 2b: Bonus/penalty sweep with best weights
    log(f"\n{'='*80}")
    log("PHASE 2b: Convergence bonus x stopword penalty sweep")
    log(f"{'='*80}")
    best_weights = weight_results[0][0]
    bonus_penalty_results = run_bonus_penalty_sweep(summaries, best_weights)

    # Phase 3: Output
    log(f"\n{'='*80}")
    log("PHASE 3: Results")
    log(f"{'='*80}")
    print_top_configs(
        weight_results, bonus_penalty_results, summaries,
        total_recall_info,
        CHANNEL_WEIGHTS, CONVERGENCE_BONUS, FUNCTION_WORD_PENALTY,
    )
    save_csv(weight_results, bonus_penalty_results, OUTPUT_DIR)

    total_elapsed = time.time() - t_start
    log(f"\n\nTotal elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    log("Done.")


if __name__ == "__main__":
    main()
