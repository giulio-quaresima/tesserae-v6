# Plan: Recall Gap Remediation

**Date:** 2026-02-17  
**Context:** Full fusion (7 channels) achieves 42.7% recall on Lucan–Vergil (91/213 gold). Miss analysis shows 137 missed pairs tractable by existing or planned channels.

**Progress (2026-02-17):**
- Phase 1: Edit channel — increased `edit_top_n` 10→100, `max_results` 10k→25k. Diagnostic: only 3/32 tractable pairs found (ranking/trigram filter limits).
- Phase 2: Semantic — `min_semantic_score` 0.6→0.5, `semantic_top_n` 50–100→100–200.
- Phase 3: Rare word — adapter in `hapax_search_direct.py`, wired in run_evaluation, run_fusion_study, run_all_channels_baseline. Returns 200 pairs for Lucan–Vergil.
- Phase 4: Rare bigram — pending (requires bigram cache).

---

## Current State

| Miss category | Count | % of missed | Intended channel |
|---------------|-------|------------|------------------|
| 1 shared lemma | 72 | 53% | Rare word (if rare) or lemma min_matches=1 |
| 2+ edit pairs | 32 | 23% | Edit distance |
| 0 shared lemmas | 65 | 47% | Semantic AI |
| Bigram parallels | — | — | Rare bigram |

**Folder structure:** `fusion_experiment/` = plans/status; `results/full_feature_test/` = output CSVs and reports. No consolidation needed; roles are distinct.

---

## Phase 1: Edit Channel Fixes

**Goal:** Catch the 32 pairs tractable by edit distance (≥2 fuzzy pairs at 0.6, or 1 exact + 1 fuzzy).

### Tasks

1. **Diagnose why edit misses them**
   - Run edit_distance alone on Lucan–Vergil with max_results=10000
   - Check whether the 32 tractable gold pairs appear in output
   - If not: inspect trigram index, token filtering, similarity threshold
   - If yes but ranked low: consider boosting edit in fusion or raising edit channel’s max_results share

2. **Config adjustments (if needed)**
   - `edit_min_shared_trigrams`: verify 1 is sufficient for short words
   - `min_edit_similarity`: 0.6 matches miss analysis; keep or lower slightly
   - Ensure `edit_include_exact=True` so 1 exact + 1 fuzzy counts as 2

3. **Re-run fusion** and confirm edit contributes more gold

---

## Phase 2: Semantic Tuning for Non-Lexical Parallels

**Goal:** Catch more of the 65 pairs with 0 shared content lemmas (thematic/structural parallels).

### Tasks

1. **Lower min_semantic_score** from 0.6 to 0.5 (or 0.55) in evaluation
   - Update `run_evaluation.py` matcher_settings when match_type == "semantic"
   - Re-run semantic channel baseline

2. **Increase semantic_top_n**
   - Current: `max(50, min(100, max_results // len(source_units)))`
   - Try 150–200 per source to surface more distant matches

3. **Verify pre-computed embeddings** for Lucan/Vergil are used (faster, same quality)

4. **Re-run fusion** and measure semantic’s contribution to the 65 non-lexical pairs

---

## Phase 3: Rare Word Channel

**Goal:** Add hapax search as a recall channel for single-word parallels when the shared lemma is rare.

### Tasks

1. **Build adapter** in `evaluation/scripts/run_evaluation.py` or new module:
   - Call hapax logic (or replicate using frequency_cache + inverted index)
   - Input: source_id, target_id, language, max_occurrences (e.g. 50)
   - Output: list of `{source: {ref}, target: {ref}}` for each (source_loc, target_loc) pair where shared lemma is rare

2. **Rarity check for 72 single-word pairs**
   - Script: for each shared lemma in missed pairs, check if it’s in rare-words cache
   - Report: how many of the 72 would be tractable by rare-word channel

3. **Wire into run_search_direct** as match_type `"rare_word"` (or `"hapax"`)

4. **Add to CHANNEL_CONFIGS** in run_fusion_study.py and run_all_channels_baseline.py

5. **Re-run baseline and fusion**

---

## Phase 4: Rare Bigram Channel

**Goal:** Add rare-bigram search as a channel. Lucan–Vergil benchmark is largely bigram parallels; rare bigrams should improve recall.

### Tasks

1. **Build adapter** for rare-bigram search:
   - Use `backend/bigram_frequency` (load_bigram_cache, extract_bigrams, get_bigram_rarity_score)
   - Or call `/rare-bigram-search` API if running with server
   - Output: `{source: {ref}, target: {ref}}` for each shared rare bigram location pair

2. **Ensure bigram cache exists** for Latin (Admin → Cache Management)

3. **Wire into run_search_direct** as match_type `"rare_bigram"`

4. **Add to CHANNEL_CONFIGS** in run_fusion_study.py and run_all_channels_baseline.py

5. **Re-run baseline and fusion**

---

## Phase 5: Optional — Lemma min_matches=1

**Goal:** Catch single-word parallels without rarity filter. High recall, high noise.

### Tasks

1. Add fusion config: `lemma_min1` = lemma with min_matches=1
2. Run as separate experiment; measure recall vs. precision
3. Decide whether to use as primary channel or only in fusion with heavy ranking/boosting

---

## Verification

After each phase:

```bash
TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/run_all_channels_baseline.py
TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/run_fusion_study.py
python evaluation/scripts/analyze_missed_pairs.py --fast
```

Target: full fusion recall > 55% on Lucan–Vergil (from 42.7%).

---

## Dependencies

| Phase | Depends on |
|-------|------------|
| 1 Edit | None |
| 2 Semantic | None |
| 3 Rare word | frequency_cache, inverted index (or hapax API) |
| 4 Rare bigram | bigram cache built for Latin |
| 5 Lemma min1 | None |

Phases 1–2 can run in parallel. Phase 3–4 need adapters; 4 requires bigram cache.
