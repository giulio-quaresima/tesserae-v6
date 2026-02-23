# Plan: AI Semantic and Dictionary Semantic Recall Testing

## Goal

Enable recall testing for both **AI semantic** (SPhilBERTa embeddings) and **intra-language dictionary** (V3 synonym pairs) match types by:

1. Copying missing production files to development
2. Implementing `find_dictionary_matches()` and wiring it
3. Updating `run_search_direct` so evaluation scripts test real semantic and dictionary channels

---

## Phase 1: Copy Production Files to Development

**Source:** `tesserae-v6/Tesserae-V6/`  
**Destination:** `tesserae-v6-dev/`

### Files to Copy

| File | Purpose |
|------|---------|
| backend/app.py | Flask app |
| backend/blueprints/search.py | Search API with semantic/edit_distance branches |
| backend/semantic_similarity.py | find_semantic_matches, find_dictionary_matches |
| backend/blueprints/batch.py | Required by app.py |
| backend/blueprints/api_docs.py | Required by app.py |
| client/src/components/search/SearchSettings.jsx | Match type dropdown UI |

---

## Phase 2: Implement Intra-Language Dictionary Matching

Add `find_dictionary_matches()` to `backend/semantic_similarity.py`:
- Uses `synonym_dict.find_synonym_pairs_in_passages`
- Filter stopwords, len > 2
- min_matches (default 2) content synonym pairs per unit pair
- Return matches with `match_basis: 'dictionary'`

Wire in `backend/blueprints/search.py` and add Dictionary option to SearchSettings.jsx.

---

## Phase 3: Wire Evaluation Pipeline

Update `run_search_direct` in `evaluation/scripts/run_evaluation.py` to branch on match_type:
- semantic → find_semantic_matches (with source_text_path, target_text_path, max_results, semantic_top_n)
- dictionary → find_dictionary_matches
- sound → matcher.find_sound_matches
- edit_distance → matcher.find_edit_distance_matches
- else → matcher.find_matches

---

## Phase 4: Verification

```bash
TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/run_all_channels_baseline.py
```

Expected: semantic and dictionary produce distinct result counts (not identical to lemma).
