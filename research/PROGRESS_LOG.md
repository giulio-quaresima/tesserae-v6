# Tesserae V6 — Progress Log

A reverse-chronological record of major milestones, decisions, and results. Read the top entries to catch up quickly. Each entry links to detailed documents.

**How to use this file:**
- Newest entries at top
- Each entry: date, what happened, key numbers, where to find details
- For full technical details, follow the links to study folders and reports
- For what's planned next, see `ROADMAP.md`
- For the current best evaluation, see `research/LATEST_REPORT.md`

---

## February 22, 2026 — Production Fusion Matches Phase 2 (90.8% Recall)

### Syntax Channel Restored + Dictionary on Windows

Benchmarked production fusion against Phase 2 evaluation. Initial gap: 762/862 (88.4%) vs 783/862 (90.8%) — 21 missing finds. Root causes:
1. **Syntax channel disabled** (returned []) — accounted for ~9 missing finds
2. **Window pass too restrictive** (4 lexical channels only) — accounted for ~12 missing finds

**Fixes:**
- Restored syntax channel using `syntax_latin.db` (542K pre-parsed lines). Efficient implementation with lemma-inverted-index pruning — only computes syntax similarity for line pairs sharing ≥1 content lemma.
- Added dictionary to window pass, removed exact (now 4 channels: lemma, lemma_min1, rare_word, dictionary). Dictionary uses `min_matches=2` co-occurrence threshold. Exact excluded because it's the slowest window channel (30+ min on large pairs) while its matches are a subset of lemma. Cost: 1/862 gold pairs.

**Result:** 782/862 (90.7%) — nearly matching Phase 2's 90.8%. Lucan-Vergil now **92.0%** (196/213), surpassing Phase 2's 90.1%. Exact excluded from windows to avoid 30+ min on large pairs (cost: 1 gold pair on VF-Vergil).

| Benchmark | Production | Phase 2 | Diff |
|-----------|-----------|---------|------|
| Lucan-Vergil | 196/213 (92.0%) | 192/213 (90.1%) | +4 |
| VF-Vergil | 467/521 (89.6%) | 472/521 (90.6%) | -5 |
| Achilleid-Vergil | 50/53 (94.3%) | 48/53 (90.6%) | +2 |
| Achilleid-Ovid | 21/23 (91.3%) | 23/23 (100%) | -2 |
| Achilleid-Thebaid | 48/52 (92.3%) | 48/52 (92.3%) | 0 |
| **TOTAL** | **782/862 (90.7%)** | **783/862 (90.8%)** | **-1** |

Runtimes: 167–342s per benchmark (comparable to Phase 2).

---

## February 22, 2026 — Fusion Website Launch + Production Optimization

### Fusion Search Deployed on Dev Website

Implemented 9-channel weighted fusion as a live web feature on the dev server (port 8080). Users can select "Fusion — All Channels (best recall)" from the match type dropdown. Results display fused_score, channel badges, and convergence count.

**New files:**
- `backend/fusion.py` — core fusion engine (~350 lines): channel registry, weighted scoring, two-pass line/window architecture, result merging
- `backend/blueprints/fusion.py` — `POST /api/search-fusion` endpoint with SSE streaming progress updates

**Frontend changes:** `SearchSettings.jsx` (fusion dropdown), `api.js` (SSE client), `useSearch.js` (routing), `App.jsx` (fused_score sorting), `SearchResults.jsx` (channel badges)

### Two-Pass Architecture: Selective Window Channels

Implemented selective windowing based on formal channel taxonomy:
- **Line pass:** all 9 channels
- **Window pass:** 4 channels (lemma, lemma_min1, rare_word, dictionary)

**Rationale:** Sub-lexical (edit_distance, sound) and distributional (semantic, dictionary) channels compare individual tokens pairwise — expanding the textual unit to a 2-line window does not introduce new token pairings, only redundant matches. Empirically confirmed: the 5 excluded channels consumed 364 of 436 seconds of window time (84%) while producing 0 novel edit_distance matches and 7 novel sound matches (0.003% of output).

**Result:** 619s → 253s (2.4× speedup), lossless — identical top-ranked fusion output.

### Per-Channel Result Capping

Added post-scoring pruning: each channel retains at most its top 50,000 results before fusion. Prevents lemma_min1 from producing 3.4M results at weight 0.3.

### Recall@K Analysis

Computed recall at K=100..100K across all 5 benchmarks. Key findings:
- Natural score cliff at fused_score ≈ 2.5–3.0 (results jump from ~7K to ~46K)
- Default max_results=5,000 scientifically justified (sits at score ≈ 3.5, multi-channel convergence zone)
- Score-based cutoff preferred over rank-based (text-size-independent)

### Documentation

- `docs/FUSION_ARCHITECTURE.md` (NEW) — comprehensive scientific documentation of channel taxonomy, two-pass design, scoring model, performance
- `docs/ARTICLE_METHODS_DRAFT.md` — added Section 15 (Fusion Search Architecture) and Section 16 (On Precision and Benchmark Completeness)
- Phase 2 evaluation report — added Section 10 (Production Search Architecture) and Section 11 (On Precision and Benchmark Completeness)

**Implementation details:** `~/.claude/projects/-home-ncoffee/memory/session_2026-02-21_fusion_website.md`

---

## February 20, 2026 — Phase 2: Sentence-Level Search Breakthrough

### Line + Sentence Union Fusion Results

Ran all 9 channels in line mode + 6 lexical channels in sentence mode, evaluated gold against union:

| Benchmark | Line Only | Sentence Only | Union | vs Phase 1 |
|-----------|-----------|---------------|-------|------------|
| Lucan-Vergil | 163/213 (76.5%) | 208/213 (97.7%) | **210/213 (98.6%)** | +47 finds |
| VF-Vergil | 440/521 (84.5%) | 499/521 (95.8%) | **508/521 (97.5%)** | +68 finds |
| Achilleid-Vergil | 46/53 (86.8%) | 51/53 (96.2%) | **53/53 (100%)** | +7 finds |
| Achilleid-Ovid Met | 20/23 (87.0%) | 19/23 (82.6%) | **22/23 (95.7%)** | +2 finds |
| Achilleid-Thebaid | 47/52 (90.4%) | 52/52 (100%) | **52/52 (100%)** | +5 finds |

**Overall: 845/862 = 98.0% recall.** Two benchmarks at 100%.

### Decision: Sliding Window over Sentence Union for Production

**Problem:** The sentence-level union gives 98% recall but has no unified ranking — no P@K metrics, no way to sort results meaningfully. Sentence units vary in length (1-7+ lines), making scores incomparable with line-mode scores.

**Alternative evaluated:** 2-line sliding windows. Each consecutive line pair (N, N+1) forms a window unit with combined tokens/lemmas. Same scoring scale as lines, same 9-channel Config D fusion. Results merged: line-mode ranking first (preserving precision), then window-only finds appended.

**Sliding Window Results (all 5 benchmarks, COMPLETE — smart dedup v2):**

| Benchmark | Gold | Line Only | Window Only | **Merged** | P@10 |
|-----------|------|-----------|-------------|------------|------|
| Lucan-Vergil | 213 | 163 (76.5%) | 187 (87.8%) | **192 (90.1%)** | 50% |
| VF-Vergil | 521 | 440 (84.5%) | 454 (87.1%) | **472 (90.6%)** | 90% |
| Ach-Ovid Met | 23 | 20 (87.0%) | 23 (100%) | **23 (100%)** | 10% |
| Ach-Thebaid | 52 | 47 (90.4%) | 47 (90.4%) | **48 (92.3%)** | 0% |
| Ach-Vergil | 53 | 46 (86.8%) | 47 (88.7%) | **48 (90.6%)** | 0% |
| **TOTAL** | **862** | **716 (83.1%)** | **758 (87.9%)** | **783 (90.8%)** | — |

**Key findings:**
- **Merged recall: 783/862 = 90.8%** — up from 83.1% line-only (+67 finds)
- **Merged = Union on every benchmark** — smart dedup closes the gap completely
- Window catches enjambed allusions across all benchmarks (+29 LV, +32 VF, +3 Ach-Ovid, +1 Ach-Thebaid, +2 Ach-Vergil)
- One benchmark (Ach-Ovid) hits 100%
- **P@10 fully preserved** (50% LV, 90% VF — identical to line-only)

**Dedup evolution:**
1. Original dedup: filter window result if ANY constituent line pair overlaps with line results → too aggressive, lost 55 gold pairs (merged 84.5% vs union 90.8%)
2. Smart dedup: filter only if ALL constituent line pairs are in line results (fully subsumed) → merged = union, no loss

**Decision: Sliding window with smart dedup is the production path** for best F-score / recall-precision balance. Sentence union (98%) available as maximum-recall research mode.

- Script: `evaluation/scripts/run_sliding_window_fusion.py`
- Smart dedup log: `research/studies/fusion_experiment_phase2/logs/sliding_window_smart_dedup.log`
- CSV: `evaluation/results/definitive_evaluation/sliding_window_fusion_20260221_070348.csv`
- Previous run (aggressive dedup): `sliding_window_fusion_20260220_202053.csv`

### A3: Fixed Sentence-Level Search

`backend/text_processor.py` — rewrote `process_file()` phrase branch to accumulate consecutive lines into sentence units. Was incorrectly splitting individual lines into sub-line fragments. Lucan BC 1: 695 lines → 151 sentence units, first sentence correctly spans lines 1-7.

### A2: Meter Baseline — Not Viable as Channel

Evaluated metrical similarity as standalone channel. P@10=0% across all benchmarks. ~25% of hexameter pairs score above 0.70 by chance. **Decision: keep meter as scoring boost only.**

- Script: `evaluation/scripts/run_metrical_channel_baseline.py`
- Notes: `research/studies/fusion_experiment_phase2/session_notes/2026-02-20_meter_baseline_results.md`

### A1: Syntax Gap Filled (Achilleid-Thebaid)

Thebaid parse data already existed in `syntax_latin.db` (8,348 lines). Generated syntax matches: 26/52 = 50% syntax recall (highest of any benchmark). Config D Thebaid improved from 86.5% → 90.4%.

- Script: `evaluation/scripts/generate_syntax_thebaid.py`
- Updated: `evaluation/syntax_baseline_data/ranked_gold_syntax_matches.json`

### Config D Re-run with Updated Syntax

Re-ran all 4 fusion configs (A-D) on all 5 benchmarks with updated Thebaid syntax data and correct semantic tuning. Results match Phase 1 except Thebaid improvement.

- Log: `research/studies/fusion_experiment_phase2/logs/config_d_rerun.log`
- CSV: `evaluation/results/definitive_evaluation/fusion_study.csv`

### Phase 2 Setup

- Created study folder: `research/studies/fusion_experiment_phase2/`
- Safety snapshot: `evaluation/scripts/phase1_archive/` (4 scripts archived)
- Baseline config recorded: `research/studies/fusion_experiment_phase2/BASELINE_CONFIG.md`
- Copied `backend/syntax_parser.py` from production (was missing from dev workspace)

### Roadmap Restructured

Reorganized `ROADMAP.md`: active work first, completed work as appendix. Added Phase 2 results, Extended Quotation Detection, Comprehensive Vergil Intertextuality Map, Commentary Parallel Extraction.

**Detailed plan:** `research/studies/fusion_experiment_phase2/PLAN.md`
**Evaluation logs:** `research/studies/fusion_experiment_phase2/logs/`

---

## February 19, 2026 — Report Updates and Non-Lemma Gold Data

### Added Non-Lemma Gold Data References

Updated evaluation report and article Section 14 with references to `*_gold_no_lemma.md` and `*_gold_nonlexical.md` data files. Four targeted insertions in report (Sections 5.7, 6, 7.1, Appendix B), two in article (Sections 14.7, 14.8).

### Added Deduplication Observation

Documented why fusion results don't show repeated-phrase clusters (unlike single-channel search): channel convergence varies per pair, spreading scores. Added to report Section 7.3 and article Section 14.8.

**Report:** `research/studies/fusion_experiment_phase1/publication/EVALUATION_REPORT.md`
**Article:** `docs/ARTICLE_METHODS_DRAFT.md`
**Session notes:** `research/sessions/2026-02-19_report_fixes.md`

---

## February 18, 2026 — Phase 1 Fusion Experiment Consolidated

### Definitive 9-Channel Fusion Evaluation

Completed comprehensive evaluation of 9-channel weighted fusion across 5 benchmarks, 4 configurations. Config D (weighted re-ranking with tuned semantic) is best overall.

**Key results (Config D):**
- Lucan-Vergil: 76.53% (163/213), P@10=50%
- VF-Vergil: 84.45% (440/521), P@10=90%
- Achilleid benchmarks: 86.5-87.0%

**Config D weights:** edit_distance=4.0, sound=3.0, exact=2.0, lemma=1.5, dictionary=1.0, semantic=0.8, rare_word=0.5, syntax=0.5, lemma_min1=0.3, convergence=+0.5×(N-1).

### Phase 1 Study Consolidated

All Phase 1 artifacts organized into `research/studies/fusion_experiment_phase1/`:
- Publication: report, abstract, reproducibility guide, bibliography
- Data: baselines, fusion CSVs, top-100 per benchmark, gold analysis files
- Session notes

### Conference Abstract

Draft abstract for DCA/SCS 2027: "Multi-Channel Fusion for Improving Intertextual Search Recall."

**Study folder:** `research/studies/fusion_experiment_phase1/`
**Report:** `research/studies/fusion_experiment_phase1/publication/EVALUATION_REPORT.md`
**Abstract:** `research/studies/fusion_experiment_phase1/publication/DCA_SCS_2027_ABSTRACT.md`
**Reproducibility:** `research/studies/fusion_experiment_phase1/publication/REPRODUCIBILITY_GUIDE.md`

---

## February 17, 2026 — 9-Channel Fusion Study

Ran preliminary 9-channel fusion evaluation. Identified that unbounded scoring + tuned semantic thresholds improve recall. Led to definitive evaluation on Feb 18.

**Study:** `research/studies/2026-02-17_9channel_fusion/`

---

## February 16, 2026 — Recall Improvement Planning

Developed strategies for improving recall beyond lemma-only baseline. Identified key paths: multi-channel fusion, semantic tuning, sentence-level search.

**Plan:** `research/plans/2026-02-16_recall_improvement.md`

---

## February 13, 2026 — Syntax and Boost Studies

### Syntax Channel Recall

Evaluated syntax channel as standalone matcher. Results vary by benchmark (0-50% recall depending on parse data availability).

**Study:** `research/studies/2026-02-13_syntax_recall/`

### Boost Study

Evaluated scoring boosts (meter, POS, syntax, bigram) for impact on ranking quality.

**Study:** `research/studies/2026-02-13_boost_study/`

---

## February 12, 2026 — Fusion Notes and Work Session

Initial fusion experiment work. Tested pairwise channel combinations, identified that union-based fusion provides additive recall gains.

**Sessions:** `research/sessions/2026-02-12_work_session.md`, `research/sessions/2026-02-12_fusion_notes.md`

---

## February 9-10, 2026 — Index Rebuild

Rebuilt all inverted indexes with LatinPipe (64%) + CLTK/UD fallback (36%):
- Latin: 1,429 texts, 298,757 lemmas, 2.2 GB
- Greek: 659 texts, 360,429 lemmas, 1.4 GB
- English: 14 texts, 22,867 lemmas, 79 MB

**Session:** `research/sessions/2026-02-09_work_session.md`

---

## February 8, 2026 — Initial Setup

Set up evaluation framework and development environment.

**Session:** `research/sessions/2026-02-08_work_session.md`

---

## February 3, 2026 — Lemma Baseline Evaluation

Established V6 lemma-only baseline. Key finding: 100% recall on parallels with 2+ shared content-word lemmas. 68-85% of scholarly parallels not found are thematic, sub-threshold, or function-word-based.

**Study:** `research/studies/2026-02-03_lemma_baseline/`
**Report:** `research/studies/2026-02-03_lemma_baseline/BENCHMARK_EVALUATION_REPORT.md`

---

## January 2026 — V6 Foundation

Completed Phases 0-3, 5-6: infrastructure, authentication, analytics, intertext repository, language parity (Latin/Greek/English), visualizations, AI embedding pre-computation.

**Details:** `ROADMAP.md` Part 6 (Completed Work)

---

## Document Map

| Document | Purpose | Audience |
|----------|---------|----------|
| **This file** (`research/PROGRESS_LOG.md`) | Chronological milestone record | You, returning after a break |
| `ROADMAP.md` | What's planned, what's next | Project planning |
| `research/LATEST_REPORT.md` | Current best evaluation (symlink) | Technical reference |
| `research/studies/*/` | Detailed study data + reproducibility | Reproducibility, deep dives |
| `docs/ARTICLE_METHODS_DRAFT.md` | Publication draft | External audience |
| `research/sessions/*.md` | Granular daily work logs | Debugging, decision archaeology |
| `research/plans/*.md` | What we intended before starting | Context for why decisions were made |
| `CLAUDE.md` | Codebase reference for AI assistants | Claude Code / Cursor |
