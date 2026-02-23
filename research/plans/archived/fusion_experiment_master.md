# Fusion Experiment — Master Plan

**Location:** `evaluation/fusion_experiment/`  
**Purpose:** Systematic testing of all Tesserae search features (recall channels and precision techniques), find optimal recall/precision combinations, implement precision improvements.

---

## 1. Feature Inventory

### Recall Channels (produce candidates)

| Channel | Implementation | Notes |
|---------|----------------|-------|
| **Lemma** | `matcher.find_matches` (match_type=lemma) | Primary; 2+ shared content words |
| **Exact** | `matcher.find_matches` (match_type=exact) | Identical word forms |
| **Semantic AI** | `find_semantic_matches` | SPhilBERTa embeddings |
| **Dictionary** | `find_dictionary_matches` | V3 synonym pairs (la/grc only) |
| **Sound** | `matcher.find_sound_matches` | Trigram similarity |
| **Edit distance** | `matcher.find_edit_distance_matches` | Fuzzy string matching |
| **Syntax** | `compute_structural_similarity` in syntax_parser.py | Standalone channel; ranks source lines per target by UD structure |
| **Rare word** | `/api/hapax-search` | Shared hapax legomena between two texts |
| **Rare pair** | `/api/rare-bigram-search` | Shared rare bigrams between two texts |

### Precision Techniques (sort/rank candidates)

| Technique | Location | Current behavior |
|-----------|----------|------------------|
| **V3 base** | scorer.py | `score = sum(IDF) / (1 + log(distance))`; `normalized_score = min(raw/max, 1.0)` |
| **Feature boosts** | feature_extractor.py | POS, edit_distance, sound, meter, syntax, bigram_boost; all cap at 1.0 |
| **Unbounded scoring** | Not implemented | Suggested: remove `min(..., 1.0)` so high scores differentiate better |

### Boost-Only (not standalone recall)

- **Meter** (`use_meter`): Hexameter pattern similarity — applies only when lemma matches exist
- **POS** (`use_pos`): Part-of-speech alignment — tie-breaker
- **Bigram boost** (`bigram_boost`): Rare co-occurring word pairs — additive to lemma score

---

## 2. Architecture

All recall channels → **Union of candidates** → V3 scoring + boosts → Ranked results

---

## 3. Infrastructure

- **Benchmarks:** `evaluation/runs/2026-02-03_v6_default_lemma_test/data/benchmarks/`
- **Scripts:** `evaluation/scripts/run_evaluation.py`, `run_all_channels_baseline.py`, `run_fusion_study.py`, `run_precision_study.py`
- **Results:** `evaluation/results/full_feature_test/`
- **Direct search:** `TESSERAE_USE_DIRECT_SEARCH=1` bypasses API for evaluation

---

## 4. Implementation Phases

### Phase 1: Extend Evaluation for All Recall Channels
- Add match_type branching in run_search_direct (lemma, exact, semantic, dictionary, sound, edit_distance)
- Add run_syntax_recall (separate pipeline)
- Add rare word/pair adapters (different data shape)

### Phase 2: Channel Fusion
- Lemma + Dictionary, Lemma + Semantic AI, Lemma + Syntax
- Lemma + Syntax + Dictionary, Full union
- Create run_fusion_study.py (configurable combinations)

### Phase 3: Precision Techniques
- Unbounded scoring option
- run_precision_study.py (capped vs unbounded)

### Phase 4: Full Factorial (Optional)
- Parameter grid: recall combinations, precision, K values for syntax

---

## 5. Sub-Plans (in plans/)

- **semantic_recall_setup.md** — AI semantic and dictionary wiring
- **combined_lemma_syntax.md** — Lemma + syntax fusion
- **syntax_recall_redo.md** — Fix syntax to rank all source lines (full corpus)
