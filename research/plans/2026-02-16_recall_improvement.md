# Recall Improvement Plan

**Created:** 2026-02-16 (Claude Code session)
**Goal:** Raise fusion recall from 42.72% to 55%+ on Lucan-Vergil benchmark (213 gold pairs)

---

## Current Baseline (2026-02-16)

| Channel | Lucan-Vergil Recall | Notes |
|---------|-------------------|-------|
| lemma | 32.4% (69/213) | min_matches=2 |
| exact | 20.7% (44/213) | min_matches=2 |
| dictionary | 17.4% (37/213) | with include_lemma_matches=True |
| sound | 9.9% (21/213) | trigram Jaccard |
| semantic AI | 6.1% (13/213) | SPhilBERTa, min_score=0.5 |
| syntax | 5.6% (12/213) | pre-computed UD parses |
| edit_distance | 2.8% (6/213) | underperforming |
| **7-channel fusion** | **42.72% (91/213)** | union, no re-ranking |

### Missed Pairs Analysis (137 missed)
- 72 (53%) share exactly 1 lemma → blocked by min_matches=2
- 32 (23%) tractable by edit distance → edit channel underperforming
- 65 (47%) share 0 content lemmas → need semantic or structural detection
- Categories overlap (a pair can be in multiple categories)

---

## Plan (Recommended Order)

### Step 1: Lemma min_matches=1 channel ← HIGHEST IMPACT
**Why first:** 72 of 137 missed pairs (53%) share exactly 1 lemma. These include real allusions built around single key words (furor, bellum, quercus, penna, clamor, gemitus, etc.). This is the single largest pool of reachable missed gold.

**Tasks:**
1. Add `lemma_min1` as a new channel in `run_all_channels_baseline.py` CHANNEL_CONFIGS
2. In `run_search_direct()`, pass `min_matches=1` in matcher_settings when match_type is `lemma_min1`
3. Run baseline — expect large candidate set (possibly 50K+), measure recall
4. Add to fusion study — measure recall lift and precision impact
5. **Do not change the default lemma channel** (min_matches=2 stays for normal use)

**Expected gain:** +15-25 percentage points on recall (many of the 72 pairs should be captured)

**Risk:** High noise. Must be paired with re-ranking (Step 3) before production use.

### Step 2: Fix edit distance channel
**Why:** 32 tractable pairs, only 6 currently found. Clear underperformance.

**Tasks:**
1. Run `evaluation/scripts/diagnose_edit_channel.py` to identify why pairs are missed
2. Lower `min_shared_trigrams` from 2 to 1 (short Latin words may share only 1 trigram)
3. Lower `min_edit_similarity` from 0.7 to 0.6 (Latin morphological variation is wide)
4. Verify `edit_include_exact=True` is working (1 exact + 1 fuzzy should count)
5. Re-run baseline and fusion

**Expected gain:** +5-10 percentage points from the 32 tractable pairs

### Step 3: Weighted fusion / re-ranking
**Why:** Before adding noisy channels (min_matches=1), need a way to combine evidence.

**Tasks:**
1. Design score normalization: each channel produces a 0-1 score per pair
2. Implement weighted combination: fused_score = sum(w_i * score_i) across channels
3. Option A (simple): hand-tuned weights based on channel precision
4. Option B (learned): logistic regression trained on gold pairs to learn optimal weights
5. Evaluate: does re-ranking improve P@50, P@100 while maintaining recall?

**Key insight:** Current fusion is union-only (first-channel-wins ordering). A weighted approach lets noisy-but-high-recall channels contribute evidence without dominating the ranking.

### Step 4: Semantic tuning
**Why:** 6.1% recall is low for AI embeddings. 65 pairs have 0 shared lemmas — these are the semantic channel's target.

**Tasks:**
1. Lower `min_semantic_score` from 0.5 to 0.4 (or even 0.35)
2. Increase `semantic_top_n` to 200+ per source line
3. Manually inspect 10-15 of the `tractability: none` missed pairs — what kind of allusion are they? (thematic, structural, phrasal, mythological reference?)
4. If many are thematic: embeddings may not help; consider LLM-based reranking as future work
5. Re-run baseline and fusion

**Expected gain:** Modest (maybe +2-5 pp). Many zero-lemma parallels may be beyond embedding reach.

### Step 5: Rare word + rare bigram adapters
**Why:** Existing hapax/rare-bigram infrastructure needs evaluation wiring.

**Tasks:**
1. Build adapter in `run_evaluation.py` for `rare_word` match_type
   - Use frequency_cache + inverted index to find shared rare lemmas
   - Output `{source: {ref}, target: {ref}}` pairs
2. Check how many of the 72 single-lemma pairs involve rare words
3. Build adapter for `rare_bigram` match_type
4. Wire both into CHANNEL_CONFIGS
5. Re-run baseline and fusion

**Expected gain:** +3-8 pp, primarily from rare single-word overlaps missed by min_matches=2

---

## Verification Protocol

After each step:
```bash
cd ~/tesserae-v6-dev
TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/run_all_channels_baseline.py
TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/run_fusion_study.py
python evaluation/scripts/analyze_missed_pairs.py --fast
```

Record results in `evaluation/results/full_feature_test/` with dated filenames.

---

## Milestones

| Milestone | Target Recall | Steps Required |
|-----------|--------------|----------------|
| Current | 42.72% | — |
| After Step 1 (lemma min1) | ~52-58% | 1 |
| After Step 2 (edit fix) | ~55-62% | 1, 2 |
| After Step 3 (re-ranking) | same recall, better precision | 1, 2, 3 |
| After Steps 4-5 | ~58-65% | 1, 2, 3, 4, 5 |

---

## Open Questions
- What is the theoretical recall ceiling for lexical/phonetic/syntactic features? (Estimated ~70% based on missed pairs analysis)
- Are the 65 zero-lemma pairs detectable by any automated method, or are they purely thematic/interpretive?
- Should we evaluate on all 3 benchmark sets simultaneously, or focus on Lucan-Vergil first?

---

## Session Log

### 2026-02-16 — Initial survey (Claude Code)
- Surveyed full codebase (production + dev)
- Mapped all 9 channels, their status, and recall numbers
- Identified min_matches=2 as the single biggest recall bottleneck
- Created this plan, CLAUDE.md, and memory files
- No code changes made
