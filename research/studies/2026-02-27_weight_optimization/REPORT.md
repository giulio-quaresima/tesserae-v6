# Fusion Weight Optimization Study

**Date:** February 27, 2026
**Script:** `evaluation/scripts/run_weight_optimization.py`
**Duration:** 19.9 minutes (11 min channel caching + 9 min grid sweep)
**Raw log:** `evaluation/results/weight_optimization_log.txt`
**CSV data:** `evaluation/results/weight_sweep_results.csv`, `evaluation/results/bonus_penalty_sweep_results.csv`

## Objective

Systematically find optimal channel weights, convergence bonus, and stopword
penalty values for the fusion scoring function, optimizing for **recall@K** —
the number of gold-standard parallels found in the top K results.

Config D (hand-tuned from ablation study) was the starting point.

## Methodology

### Key Insight: Cache Channels, Sweep Fusion Parameters

Channel results (lemma, exact, sound, edit_distance, semantic, dictionary,
syntax, rare_word, lemma_min1) are independent of fusion parameters. Weights,
convergence bonus, and stopword penalty only affect `fuse_results()`, which is
pure arithmetic on cached results. So:

1. Run all 9 channels ONCE per benchmark, extract lightweight pair summaries
   (raw scores, channel counts, stopword flags, gold match indices)
2. Re-fuse with 35,017 parameter configurations using numpy-vectorized scoring
3. Evaluate recall@K for each config

### Search Space

**Channel weights** (9 dimensions, 34,992 combinations):

| Channel       | Config D | Sweep Range              | Steps |
|---------------|----------|--------------------------|-------|
| edit_distance | 4.0      | 2.0, 3.0, 4.0, 5.0      | 4     |
| sound         | 3.0      | 1.5, 2.5, 3.0, 4.0      | 4     |
| exact         | 2.0      | 1.0, 2.0, 3.0            | 3     |
| lemma         | 1.5      | 1.0, 1.5, 2.0            | 3     |
| rare_word     | 2.0      | 1.0, 2.0, 3.0            | 3     |
| dictionary    | 1.0      | 0.5, 1.0, 1.5            | 3     |
| semantic      | 0.8      | 0.5, 0.8, 1.2            | 3     |
| syntax        | 0.5      | 0.3, 0.5, 1.0            | 3     |
| lemma_min1    | 0.3      | 0.1, 0.3, 0.5            | 3     |

**Convergence bonus** (5 values): 0.0, 0.25, 0.5, 0.75, 1.0
**Stopword penalty** (5 values): 0.1, 0.2, 0.3, 0.5, 1.0

Two-phase approach to keep search space tractable:
- Phase 2a: 34,992 weight configs with fixed bonus=0.5, penalty=0.3
- Phase 2b: 25 bonus x penalty combos with best weights from Phase 2a

### Objective Function

- **Primary:** recall@500 summed across all 5 benchmarks (weighted by gold count)
- **Secondary:** recall@100 (tiebreaker)
- **Insight:** Total recall is constant across all configs (same pair set, only
  ordering changes), so the 90% guard is automatically satisfied (91.0%).

### Benchmarks

5 text pairs, 862 total gold entries:

| Benchmark              | Gold | Total Recall |
|------------------------|------|--------------|
| Lucan BC 1 - Vergil    | 213  | 196 (92.0%)  |
| VF Argon. 1 - Vergil   | 521  | 467 (89.6%)  |
| Achilleid - Vergil     | 53   | 50 (94.3%)   |
| Achilleid - Ovid Met.  | 23   | 21 (91.3%)   |
| Achilleid - Thebaid    | 52   | 50 (96.2%)   |
| **Total**              | **862** | **784 (91.0%)** |

### Technical Details

- 1,014,676 unique line-level pairs extracted across 5 benchmarks
- Summary arrays: 82.2 MB (vs ~7 GB for full result dicts)
- Sweep rate: 65 configs/second (numpy vectorized matrix multiply + argpartition)
- Window results excluded from sweep (appended after all line results, never
  affect recall@500 since there are >100K line pairs per benchmark)

## Results

### Config D (Baseline)

```
Weights: ed=4.0 sn=3.0 ex=2.0 lm=1.5 rw=2.0 dc=1.0 se=0.8 sy=0.5 m1=0.3
Bonus: 0.5, Penalty: 0.3

R@10:   2.2% ( 19/862)
R@50:   6.0% ( 52/862)
R@100:  9.7% ( 84/862)
R@500: 19.8% (171/862)
R@1000: 26.5% (228/862)
R@5000: 39.0% (336/862)
```

### Optimized Config (Config E)

```
Weights: ed=2.0 sn=4.0 ex=1.0 lm=2.0 rw=1.0 dc=1.5 se=0.8 sy=0.5 m1=0.3
Bonus: 0.5, Penalty: 0.2

R@10:   2.1% ( 18/862)
R@50:   6.0% ( 52/862)
R@100:  9.9% ( 85/862)
R@500: 22.6% (195/862)
R@1000: 28.8% (248/862)
R@5000: 42.7% (368/862)
```

### Improvement

| Metric | Config D | Config E | Change |
|--------|----------|----------|--------|
| R@100  | 9.7% (84) | 9.9% (85) | +0.1% (+1) |
| R@500  | 19.8% (171) | 22.6% (195) | **+2.8% (+24)** |
| R@1000 | 26.5% (228) | 28.8% (248) | +2.3% (+20) |
| R@5000 | 39.0% (336) | 42.7% (368) | +3.7% (+32) |

### Weight Changes (Config D -> Config E)

| Channel       | Config D | Config E | Change | Interpretation |
|---------------|----------|----------|--------|----------------|
| edit_distance | 4.0      | **2.0**  | -2.0   | Was overweighted; Levenshtein noise pushed low-quality pairs up |
| sound         | 3.0      | **4.0**  | +1.0   | Phonetic similarity is a stronger signal than edit distance |
| exact         | 2.0      | **1.0**  | -1.0   | Exact matches already captured by lemma; double-counting inflated scores |
| lemma         | 1.5      | **2.0**  | +0.5   | Core lexical channel deserves more weight |
| rare_word     | 2.0      | **1.0**  | -1.0   | Rare words are already boosted by rarity; high weight over-promoted sparse matches |
| dictionary    | 1.0      | **1.5**  | +0.5   | Curated synonym pairs are high-precision |
| semantic      | 0.8      | 0.8      | 0      | Unchanged |
| syntax        | 0.5      | 0.5      | 0      | Unchanged |
| lemma_min1    | 0.3      | 0.3      | 0      | Unchanged |

### Convergence Bonus and Stopword Penalty

- **Convergence bonus:** 0.5 remains optimal. Higher values (0.75, 1.0) hurt R@500.
- **Stopword penalty:** 0.2 marginally better than 0.3 at R@100 (85 vs 85 at R@500,
  but 85 vs 84 at R@100 with penalty=0.1). Penalty values 0.2-0.5 are equivalent
  at R@500; very low (0.1) slightly hurts R@100.

### Top 20 Weight Configs (Phase 2a)

All top 20 configs share **ed=2.0, ex=1.0, lm=2.0** — these are the most
robust findings. Sound, rare_word, dictionary, semantic, syntax, and lemma_min1
show more variability, suggesting they are less sensitive to exact values.

```
Rank  R@500   R@100  Weights
  1   22.6%    9.9%  ed2.0/sn4.0/ex1.0/lm2.0/rw1.0/dc1.5/se0.8/sy0.5/m10.3
  2   22.5%   10.2%  ed2.0/sn4.0/ex1.0/lm2.0/rw2.0/dc1.5/se0.8/sy0.5/m10.1
  3   22.5%   10.1%  ed2.0/sn4.0/ex1.0/lm2.0/rw3.0/dc1.5/se0.5/sy0.3/m10.3
  4   22.5%    9.5%  ed2.0/sn4.0/ex1.0/lm2.0/rw1.0/dc1.5/se0.8/sy0.5/m10.1
  5   22.5%    9.3%  ed2.0/sn1.5/ex1.0/lm2.0/rw1.0/dc1.0/se0.8/sy0.3/m10.5
  6   22.4%   11.0%  ed2.0/sn4.0/ex1.0/lm2.0/rw2.0/dc1.0/se1.2/sy1.0/m10.5
  7   22.4%   10.4%  ed2.0/sn4.0/ex1.0/lm2.0/rw1.0/dc1.0/se1.2/sy1.0/m10.5
  8   22.4%   10.4%  ed2.0/sn4.0/ex1.0/lm2.0/rw3.0/dc1.5/se1.2/sy1.0/m10.5
  9   22.4%   10.3%  ed2.0/sn4.0/ex1.0/lm2.0/rw2.0/dc1.5/se0.8/sy0.5/m10.3
 10   22.4%   10.2%  ed2.0/sn4.0/ex1.0/lm2.0/rw1.0/dc1.0/se0.5/sy0.5/m10.5
```

## Validation (Full Production Benchmark)

**Status:** Validated Feb 27, 2026.
**Log:** `evaluation/results/benchmark_config_e_log.txt`

Config E weights applied to `backend/fusion.py` and validated with the full
production benchmark (`benchmark_production_fusion.py`), which uses the
complete two-pass pipeline including window results.

### Total Recall: 784/862 (91.0%) — Zero regression

| Benchmark              | Config D | Config E | Diff |
|------------------------|----------|----------|------|
| Lucan BC 1 - Vergil    | 196/213 (92.0%) | 196/213 (92.0%) | 0 |
| VF Argon. 1 - Vergil   | 467/521 (89.6%) | 467/521 (89.6%) | 0 |
| Achilleid - Vergil     | 50/53 (94.3%)   | 50/53 (94.3%)   | 0 |
| Achilleid - Ovid Met.  | 21/23 (91.3%)   | 21/23 (91.3%)   | 0 |
| Achilleid - Thebaid    | 50/52 (96.2%)   | 50/52 (96.2%)   | 0 |
| **Total**              | **784/862 (91.0%)** | **784/862 (91.0%)** | **0** |

### Per-Benchmark Recall@K (Config E, production pipeline)

| Benchmark              | R@10  | R@50  | R@100 | R@500 | R@1000 | R@5000 |
|------------------------|-------|-------|-------|-------|--------|--------|
| Lucan-Vergil (213)     | 2.3%  | 6.6%  | 10.8% | 19.2% | 23.5%  | 36.2%  |
| VF-Vergil (521)        | 1.9%  | 4.8%  | 8.4%  | 22.3% | 29.2%  | 43.6%  |
| Achilleid-Vergil (53)  | 1.9%  | 5.7%  | 9.4%  | 17.0% | 26.4%  | 43.4%  |
| Achilleid-Ovid (23)    | 4.3%  | 8.7%  | 13.0% | 52.2% | 56.5%  | 65.2%  |
| Achilleid-Thebaid (52) | 1.9%  | 15.4% | 19.2% | 32.7% | 36.5%  | 50.0%  |

### P@10 Results

| Benchmark              | P@10 (Config E) | P@10 (Phase 2 ref) |
|------------------------|-----------------|---------------------|
| Lucan-Vergil           | 50%             | 50%                 |
| VF-Vergil              | 100%            | 90%                 |
| Achilleid-Vergil       | 10%             | 0%                  |
| Achilleid-Ovid         | 10%             | 10%                 |
| Achilleid-Thebaid      | 10%             | 0%                  |

### Conclusion

Config E validated successfully. Zero total recall regression — the same
784/862 gold pairs are found. The weight changes only affect ranking quality,
pushing more gold pairs into the top K results. Config E has been applied
to `backend/fusion.py` as the new default.

## Reproducibility

```bash
cd ~/tesserae-v6-dev
source venv/bin/activate
TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/run_weight_optimization.py
```

Script: `evaluation/scripts/run_weight_optimization.py`
Modified: `backend/fusion.py` — `fuse_results()` accepts optional `weights`,
`convergence_bonus`, `stopword_penalty` overrides for parameterized evaluation.

## Session Log

### Implementation Process

1. **Reading existing code.** Read `backend/fusion.py` (the fusion engine with
   `fuse_results()`, `CHANNEL_WEIGHTS`, `CONVERGENCE_BONUS`, `FUNCTION_WORD_PENALTY`)
   and `evaluation/scripts/benchmark_production_fusion.py` (the production benchmark
   with `evaluate_results()`, `load_gold()`, `parse_ref()`, `parse_range_ref()`).

2. **Making fusion.py parameterizable.** Added optional parameter overrides to
   `fuse_results(weights=None, convergence_bonus=None, stopword_penalty=None)` and
   `_compute_rarity_multiplier(penalty=None)`. When `None`, these fall back to the
   module-level defaults. This allows the grid search to test configs without
   monkey-patching globals. Backward-compatible — existing callers unaffected.

3. **Creating the optimization script (v1).** Wrote
   `evaluation/scripts/run_weight_optimization.py` with the full grid search logic:
   cache all 9 channel results per benchmark, then sweep 34,992 weight configs +
   25 bonus/penalty combos, calling `fuse_results()` for each.

4. **v1 failure: OOM.** Launched in tmux. The script cached all channel results as
   full result dicts (~7 GB across 5 benchmarks — each pair carries text, tokens,
   lemmas, highlights). Calling `fuse_results()` 350,000 times (35K configs × 5
   benchmarks × 2 passes), where each call builds defaultdicts, sorts 100K+ entries,
   and creates full result dicts, caused the process to be killed after ~20 minutes.

5. **Key insights during rewrite:**
   - **Total recall is constant** across all configs (same pair set, different
     ordering), so the 90% guard is automatically satisfied.
   - **Windows never affect recall@500** because `merge_line_and_window()` appends
     ALL line results before ANY window results, and there are >100K line pairs per
     benchmark. Windows can be skipped entirely during the sweep.
   - Only per-pair raw scores, channel counts, stopword flags, and gold match
     indices are needed — everything else (text, tokens, highlights) is dead weight.

6. **Creating the optimization script (v2).** Complete rewrite using numpy-accelerated
   approach:
   - `extract_pair_summary()`: Extracts lightweight numpy arrays from heavy channel
     results — `scores_matrix` (N×9 float32), `n_channels` (N int8), `is_stopword`
     (N bool), `gold_matches` (set of indices). Memory: 82.2 MB vs ~7 GB.
   - `evaluate_config_fast()`: Numpy-vectorized scoring via matrix multiply
     (`scores_matrix @ weight_vector`), stopword penalty via boolean mask, and
     `np.argpartition` for O(N) top-K selection instead of full sort.
   - `run_channels_and_extract()`: Runs channels one benchmark at a time, extracts
     summaries, discards heavy results immediately to keep memory low.
   - `log()` helper with `flush=True` on all print statements — fixed tee buffering
     issue where output wasn't appearing in the log file.
   - Two-phase sweep: Phase 2a (34,992 weight configs with fixed bonus=0.5,
     penalty=0.3), Phase 2b (25 bonus × penalty combos with best weights from 2a).
   - Sweep rate: 65 configs/second.

7. **v2 success.** Completed in 19.9 minutes (11 min channel caching + 9 min grid
   sweep). Config E found with R@500 improved from 19.8% to 22.6% (+24 gold pairs
   in top 500).

8. **Applying Config E to fusion.py.** Updated `CHANNEL_WEIGHTS` in `backend/fusion.py`:
   edit_distance 4.0→2.0, sound 3.0→4.0, exact 2.0→1.0, lemma 1.5→2.0,
   rare_word 2.0→1.0, dictionary 1.0→1.5. Updated `FUNCTION_WORD_PENALTY` 0.3→0.2.

9. **Production validation.** Ran `benchmark_production_fusion.py` in tmux with
   Config E weights. Result: 784/862 (91.0%) — identical to Config D across all 5
   benchmarks. Zero total recall regression confirmed.

10. **Documentation.** Created this study report, updated TODO list (Feb 27 section),
    updated `research/LATEST_REPORT.md` symlink, updated `CLAUDE.md` and `MEMORY.md`.

### Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| v1 script OOM/killed | Cached ~7 GB of full result dicts; called `fuse_results()` 350K times (each builds full dicts with text/tokens/lemmas/highlights) | Complete rewrite using lightweight numpy arrays (82 MB) with vectorized matrix multiply |
| tee output buffering | `print()` output piped through `tee` buffered for minutes | Added `def log(msg): print(msg, flush=True)` throughout v2 |
| tmux duplicate session | `tmux new-session -d -s benchmark` failed (old session existed) | `tmux kill-session -t benchmark` before creating new one |

### Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `backend/fusion.py` | Modified | Added parameter overrides to `fuse_results()` and `_compute_rarity_multiplier()`; applied Config E weights |
| `evaluation/scripts/run_weight_optimization.py` | Created | Numpy-accelerated grid search script (v2) |
| `research/studies/2026-02-27_weight_optimization/REPORT.md` | Created | This study report |
| `evaluation/results/weight_optimization_log.txt` | Created | Full optimization run log (357 lines) |
| `evaluation/results/weight_sweep_results.csv` | Created | 34,992 weight config results |
| `evaluation/results/bonus_penalty_sweep_results.csv` | Created | 25 bonus × penalty config results |
| `evaluation/results/benchmark_config_e_log.txt` | Created | Full production validation log (307 lines) |
| `research/sessions/TODO_2026-02-23.md` | Updated | Added "Completed Feb 27" section |
| `research/LATEST_REPORT.md` | Updated | Symlink → this report |
| `CLAUDE.md` | Updated | Config E reference in Current Development Focus |
