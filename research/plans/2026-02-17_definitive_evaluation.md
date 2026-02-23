# Definitive Evaluation Pipeline Plan

**Date:** February 17, 2026
**Purpose:** Single, reproducible, peer-review-ready evaluation of Tesserae V6 intertext matching

## Context

Previous evaluation runs had methodological problems:
- Achilleid benchmark `type: 4` was **fabricated** (xlsx has TYPE=None for all entries; real quality signal is AUTH field with commentator citations)
- Semantic channel was tuned on Lucan-Vergil only, then applied to all benchmarks
- Syntax labels had a dot-vs-underscore mismatch, silently returning empty for Achilleid benchmarks
- Thebaid (362 entries, the largest Achilleid target work) was excluded
- rare_word channel not included in fusion evaluation
- VF benchmark filename inconsistency between scripts

This plan creates a single pipeline that runs end-to-end in tmux.

---

## Benchmark Gold Standards

### Lucan-Vergil (unchanged)
- **Source:** `bench41.txt` — 3,410 entries, types 1-5
- **Gold criterion:** Types 4-5 (strong lexical parallels)
- **Commentators:** Roche, Wick/Viansino, Haskins, Teubner-Braun
- **Gold count:** 213 entries

### VF-Vergil (unchanged)
- **Source:** `vf_intertext_dataset_2_0.tab` — 945 entries
- **Gold criterion:** Commentary-attested (Kleywegt, Zissos, Spaltenstein), Vergil-only subset
- **No type scoring** (binary classification)
- **Gold count:** 521 entries

### Achilleid (REBUILT from original xlsx)
- **Source:** `Stat.Achilleid1.benchmark.xlsx` (Geneva 2015 seminar)
- **Gold criterion:** 2+ unique commentators from {D=Dilke, N=Nuzzo, R-S=Ripoll-Soubiran, U=Uccellini}
- **Exclusions:** Self-references (SOURCE=statius.achilleid), uncertain entries (NOTE="?")
- **Deduplication:** Rows with same (achilleid_line, source_work, source_line) merged, AUTH values unioned
- **Previous `type: 4` was fabricated during conversion — original xlsx has TYPE=None for all entries**

| Sub-benchmark | Gold (2+ commentators) | Total (deduped) |
|---------------|----------------------|-----------------|
| Achilleid-Vergil | 53 | 216 |
| Achilleid-Ovid Metamorphoses | 23 | 148 |
| Achilleid-Thebaid | 52 | 252 |
| Achilleid-Heroides | **0** (excluded) | 39 |

**Note:** Achilleid gold sets are small. P@K metrics will be noisy. Heroides drops out entirely (no entries have 2+ commentators).

---

## Pipeline Phases

### Phase 0: Benchmark Preparation (~10 seconds)
**Script:** `evaluation/scripts/prepare_benchmarks.py`

1. Parse Achilleid xlsx directly
2. Exclude self-references and NOTE="?" entries
3. Deduplicate by (achilleid_line, source_work, source_line), merge AUTH
4. Filter to 4 target works (correcting "thebiad" → "thebaid" typo)
5. Filter to 2+ unique commentators = GOLD
6. Output to `evaluation/benchmarks/achilleid_gold_2plus_commentators.json`
7. Copy Lucan/VF benchmarks to `evaluation/benchmarks/` (canonical location)
8. Write `evaluation/benchmarks/BENCHMARK_METHODOLOGY.md`

### Phase 1: Per-Channel Baselines (~40-50 min)
**Script:** `evaluation/scripts/run_definitive_baselines.py`

9 channels x 5 benchmarks = 45 evaluations

| Channel | Key Settings |
|---------|-------------|
| lemma | min_matches=2, max_results=10000 |
| lemma_min1 | min_matches=1, max_results=50000 |
| exact | min_matches=2 |
| semantic | default (min_sem=2, threshold=0.92) |
| dictionary | min_matches=2, include_lemma |
| sound | default threshold |
| edit_distance | similarity=0.6, trigrams=1, include_exact=True, top_n=100 |
| syntax | pre-computed (no Thebaid data available) |
| rare_word | max_occurrences=50 |

**Output:** `evaluation/results/definitive_evaluation/baselines.csv`

### Phase 2: Semantic Tuning (~20-30 min)
**Script:** `evaluation/scripts/run_definitive_tuning.py`

6 configs x 5 benchmarks = 30 evaluations

| Config | min_semantic_matches | semantic_only_threshold |
|--------|---------------------|------------------------|
| default | 2 | 0.92 |
| 1match | 1 | 0.92 |
| 0match_high | 0 | 0.85 |
| 0match_mid | 0 | 0.80 |
| 1match_low | 1 | 0.80 |
| 0match_low | 0 | 0.70 |

**Selection:** Best chosen by recall on Lucan-Vergil. Validated on VF-Vergil. Achilleid reported as supplementary.

**Output:** `semantic_tuning.csv` + `semantic_tuning_selection.json`

### Phase 3: Fusion Study (~1.5-2 hours)
**Script:** `evaluation/scripts/run_definitive_fusion.py`

4 configs x 5 benchmarks = 20 evaluations

| Config | Scoring | Semantic | Fusion Method |
|--------|---------|----------|---------------|
| A: Default baseline | Capped | Default | Union (first-seen) |
| B: Unbounded | Unbounded | Default | Union (first-seen) |
| C: Unbounded + tuned | Unbounded | Lucan-tuned | Union (first-seen) |
| D: Weighted | Unbounded | Lucan-tuned | Weighted rerank |

**Output:** `fusion_study.csv`

### Phase 4: Report Generation (~10 seconds)
**Script:** `evaluation/scripts/generate_definitive_report.py`

Reads all CSVs, generates `EVALUATION_REPORT.md` with:
1. Full methodology (benchmark construction, gold criteria, channel descriptions)
2. Per-channel baseline matrix
3. Semantic tuning results + selection rationale
4. Fusion comparison table
5. Comparison to previous best (Feb 17: 76.53% Lucan, 84.45% VF)
6. Limitations and caveats
7. Reproducibility instructions

---

## Files Created/Modified

### New files (6 scripts + 1 shell):
- `evaluation/scripts/prepare_benchmarks.py`
- `evaluation/scripts/run_definitive_baselines.py`
- `evaluation/scripts/run_definitive_tuning.py`
- `evaluation/scripts/run_definitive_fusion.py`
- `evaluation/scripts/generate_definitive_report.py`
- `evaluation/scripts/run_definitive_pipeline.sh`

### Modified (1 file):
- `evaluation/scripts/run_evaluation.py` — fix `load_syntax_found_pairs()` label matching (dot vs underscore normalization)

### New output directory:
- `evaluation/benchmarks/` — canonical benchmark location
- `evaluation/results/definitive_evaluation/` — all results

---

## How to Run

```bash
tmux new-session -d -s definitive "cd ~/tesserae-v6-dev && bash evaluation/scripts/run_definitive_pipeline.sh 2>&1; echo DONE; sleep 86400"
```

**Monitor:**
```bash
tmux capture-pane -t definitive -p -S -30
```

**Estimated total runtime:** 2.5-3.5 hours

---

## Verification Checklist

- [ ] `evaluation/benchmarks/BENCHMARK_METHODOLOGY.md` documents all gold criteria
- [ ] `baselines.csv` has 45 rows (9 channels x 5 benchmarks)
- [ ] `semantic_tuning.csv` has 30 rows (6 configs x 5 benchmarks)
- [ ] `fusion_study.csv` has 20 rows (4 configs x 5 benchmarks)
- [ ] `EVALUATION_REPORT.md` has all methodology sections
- [ ] Lucan-Vergil fusion recall in ~70-80% range (consistent with previous 76.53%)
- [ ] Achilleid gold counts: 53 (Vergil), 23 (Ovid Met), 52 (Thebaid)
- [ ] Heroides correctly excluded with documentation
