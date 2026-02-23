# Fusion Experiment — Channel Status

**Last updated:** 2026-02-16  
**Reference:** Run `TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/run_all_channels_baseline.py`

---

## Setup Verification (Production → Dev Transfer)

| File | In dev? | Notes |
|------|---------|-------|
| backend/app.py | Yes | Has create_app() |
| backend/blueprints/search.py | Yes | Semantic + dictionary branches (streaming + non-streaming) |
| backend/semantic_similarity.py | Yes | find_semantic_matches, find_dictionary_matches, find_dictionary_crosslingual_matches |
| backend/blueprints/batch.py | Yes | Required by app |
| backend/blueprints/api_docs.py | Yes | Required by app |
| backend/embedding_storage.py | Yes | Pre-computed embeddings; used when available |
| client/SearchSettings.jsx | Yes | AI Semantic + Dictionary (V3 Synonyms) options |
| backend/synonymy/*.csv | Yes | fixed_latin_syn.csv, fixed_greek_syn.csv, greek_latin_dict.csv |
| sentence-transformers | Yes | **Added to requirements.txt** (was missing); required for AI semantic |

**Note:** Production has `find_dictionary_crosslingual_matches` (Greek–Latin) but NOT `find_dictionary_matches` (intra-language). Dev has both; intra-language dictionary was implemented in dev.

**Verified 2026-02-16:** AI semantic and dictionary both run successfully. Pre-computed embeddings exist for Lucan/Vergil (uses them). sentence-transformers installed.

---

## Recall Channels (9 total)

| # | Channel | Wired in run_search_direct? | max_results passed? | Run in baseline? | Lucan–Vergil recall | Notes |
|---|---------|----------------------------|---------------------|------------------|---------------------|------|
| 1 | **Lemma** | Yes (default) | N/A | Yes | 32.4% | Working |
| 2 | **Exact** | Yes | N/A | Yes | 20.7% | Working |
| 3 | **Semantic AI** | Yes | Yes (fixed Feb 12) | Yes | 6.1% | Working; uses pre-computed embeddings when available |
| 4 | **Dictionary** | Yes | No (0=no limit) | Yes | 18.3% | Evaluation uses include_lemma_matches=True; website uses synonym-only |
| 5 | **Sound** | Yes | Yes | Yes | 9.9% | max_results passed in run_search_direct |
| 6 | **Edit distance** | Yes | Yes | Yes | 2.8% | max_results passed in run_search_direct |
| 7 | **Syntax** | No (separate pipeline) | — | **Yes** | 5.6% | Pre-computed from syntax_examples_all_benchmarks.json (full-corpus ranking, 2026-02-15) |
| 8 | **Rare word** | No | — | No | — | Different API; needs adapter |
| 9 | **Rare pair** | No | — | No | — | Different API; needs adapter |

---

## Boost-Only (3 total)

| # | Technique | Role | Status |
|---|-----------|------|--------|
| 10 | **Meter** | Hexameter similarity when lemma matches exist | Implemented as boost |
| 11 | **POS** | Part-of-speech alignment | Implemented as boost |
| 12 | **Bigram boost** | Rare co-occurring word pairs | Implemented as boost |

---

## Precision Techniques (3 total)

| # | Technique | Status |
|---|-----------|--------|
| 13 | **V3 base** (IDF + distance) | Implemented |
| 14 | **Feature boosts** | Implemented |
| 15 | **Unbounded scoring** | Planned; not implemented |

---

## Development Needed

### Immediate (semantic matching)
1. ~~Dictionary without lemma exclusion~~ — **Done:** Evaluation uses include_lemma_matches=True for dictionary

### Sound & Edit distance
3. ~~Pass max_results~~ — **Done:** run_search_direct passes max_results for sound and edit_distance

### Syntax
4. ~~Integrate syntax into recall pipeline~~ — **Done:** syntax merged from `syntax_channel_baseline.csv` (source: syntax_examples_all_benchmarks.json, full-corpus ranking fix Feb 2026)

### Rare word/pair
5. Build adapters to convert word lists → (source_line, target_line) candidates

---

## Key Paths

| Purpose | Path |
|---------|------|
| Evaluation scripts | `evaluation/scripts/run_evaluation.py`, `run_all_channels_baseline.py`, `run_fusion_study.py` |
| Semantic matching | `backend/semantic_similarity.py` |
| Synonym data | `backend/synonymy/fixed_latin_syn.csv`, `fixed_greek_syn.csv` |
| Benchmarks | `evaluation/runs/2026-02-03_v6_default_lemma_test/data/benchmarks/` |
| Results | `evaluation/results/full_feature_test/` |
| Syntax pre-computed | `evaluation/results/syntax_recall_2026-02-13/syntax_channel_baseline.csv` |
