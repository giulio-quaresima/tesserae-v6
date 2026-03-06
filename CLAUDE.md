# Tesserae V6

## What This Is
Intertext matching tool for Latin, Greek, and English texts. Detects textual parallels (allusions, echoes, borrowings) across a corpus of 2,100+ classical literary works. Free and open web application for scholars.

## Architecture
- **Backend:** Flask (Python), PostgreSQL, blueprints in `backend/blueprints/`
- **Frontend:** React 18 + Vite 5 + Tailwind CSS 3, built to `dist/`
- **Entry point:** `main.py` starts Flask on port 5000

## Key Backend Files
| File | Purpose |
|------|---------|
| `backend/app.py` | Flask app factory, registers all blueprints |
| `backend/matcher.py` | Core matching: lemma, exact, sound, edit_distance |
| `backend/scorer.py` | V3 scoring: IDF + distance, boosts (meter, POS, bigram) |
| `backend/semantic_similarity.py` | AI semantic (SPhilBERTa) + dictionary (V3 synonyms) |
| `backend/text_processor.py` | Tokenization, lemmatization (CLTK/lookup tables) |
| `backend/feature_extractor.py` | Feature boosts (POS, trigrams, meter, syntax) |
| `backend/blueprints/search.py` | `/api/search` endpoint |
| `backend/blueprints/hapax.py` | Rare word + rare bigram search |

## Search Channels (9 total)
1. **lemma** — 2+ shared dictionary forms (default, min_matches=2)
2. **exact** — 2+ identical surface tokens
3. **sound** — character trigram Jaccard similarity
4. **edit_distance** — Levenshtein fuzzy matching (Filum-like)
5. **semantic** — SPhilBERTa cosine similarity (AI embeddings)
6. **dictionary** — V3 synonym pairs from `backend/synonymy/` CSVs
7. **syntax** — UD dependency pattern matching (pre-computed)
8. **rare_word** — shared hapax legomena
9. **rare_pair** — shared rare bigrams

## Evaluation Infrastructure
- Scripts: `evaluation/scripts/`
- Benchmarks: `evaluation/benchmarks/`
- Latest report: `research/LATEST_REPORT.md` (symlink to latest study)
- All studies: `research/studies/`
- Run without server: `TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/run_all_channels_baseline.py`

## Regression Tests
**Before completing any task that touches search, indexing, or text processing code**, run the reference tests in `tests/search_reference_tests.md`. The "arma virum" search must return Ovid, Quintilian, Seneca. Do NOT mark tasks complete if these tests fail.

## Data Files (not in git, large)
- `backend/embeddings/` (~2GB) — pre-computed semantic embeddings
- `data/inverted_index/` (~2.4GB) — search index (symlinked to `/var/www/tesseraev6_flask/data/inverted_index/`)
- `data/lemma_tables/` — Latin/Greek lemma lookup tables (61K+ Latin, 58K+ Greek)
- `cache/lemmas/` — pre-computed per-file lemmatizations (server loads from these, not .tess files). **Must be rebuilt when lemmatization logic changes.**
- `cache/bigrams/` (~565MB) — bigram indexes
- `texts/` (~308MB) — corpus .tess files

## Lemmatization Pipeline
Latin lemmatization uses a two-tier system:
1. **Primary:** UD treebank lookup table (`data/lemma_tables/latin_lemmas.json`, 61K+ entries)
2. **Fallback:** CLTK LatinBackoffLemmatizer (for forms not in table)
3. **Post-processing:** Trailing sense digits stripped (e.g., `effero1` → `effero`)
4. **Optional:** LatinPipe syntax DB (`syntax_latin.db`) overrides at index-build time

When modifying lemmatization: update the lemma table, rebuild inverted index, AND clear/rebuild lemma cache (`cache/lemmas/`).

## Environment Variables
- `DATABASE_URL` — PostgreSQL connection string
- `SESSION_SECRET` — Flask session secret
- `ADMIN_PASSWORD` — admin panel access

## Current Development Focus
Fusion search is live on the dev website. Production fusion: **92.8% recall** across 5 benchmarks (800/862). Lucan-Vergil: 91.5% (195/213), Achilleid-Thebaid: 96.2% (50/52) — both surpass Phase 2. Key improvements: restored syntax channel (DB-backed), dictionary on windows, channel optimizations (dictionary inverted-index 850x, lemma_min1 IDF pre-filter 20x, syntax caching+multiprocessing). **Pair-size gates removed** -- all 9 channels run unconditionally on every text pair. Aeneid x Metamorphoses completes in ~12 min with all channels. Progressive SSE streaming with "Pause updates" button. **Rarity scoring (current, commit `bc7e937`):** Three-layer system using geometric mean corpus-IDF (1,429 Latin texts): (1) **squared base multiplier** -- common-word pairs reduced proportionally; (2) **min-word-IDF-weighted convergence** -- `min(1.0, min_word_idf)^2` (Zipf-like scaling); (3) **convergence-scaled rarity boost** -- rare multi-channel pairs boosted. **Function-word detection:** Uses curated stoplist from `backend/matcher.py` (66 Latin, 88 Greek, 60 English function words) instead of IDF threshold. `n_content_words` counted from unique surface word sets (not lemma dict, to avoid duplicates like fata/fatum). Min-IDF gate removed entirely -- stoplist gives precise function-word identification. **Three penalty tiers:** (1) single-word matches get `SINGLE_WORD_PENALTY=0.12`; (2) all-function-word matches get `NO_SIGNIFICANT_WORDS_PENALTY=0.50` + convergence zeroed; (3) mixed function+content matches get `SINGLE_WORD_PENALTY` + convergence zeroed. `RARITY_IDF_FLOOR=0.05`. **Convergence zeroing:** `weighted_n=0` when `n_unique_words<=1` OR `n_content_words==0` OR mixed function+content. **Headword IDF normalization:** `_get_corpus_doc_freqs()` uses `max(lemma_df, headword_df)` via `latin_lemmas.json`. Cross-text-pair validated: Aen 1×BC 1 ("pectore curas" #30), Aen 7×Punica 2 ("Acheronta movebo" #13), Aen 5×Theb 6 ("obstipuere animi / ingentia~silentia" #10, 7ch). `ubi+fata`, `nec+priorem`, `tum+vires` suppressed from top 50 to below rank 500. Channel weights: ed=2.0, sn=4.0, ex=1.0, lm=2.0, rw=2.0, dc=0.5, se=1.2, sy=0.3, ss=0.5, m1=0.3. Convergence bonus=0.75. Total recall: 800/862 (92.8%). Study report: `research/studies/2026-03-02_common_word_suppression/REPORT.md`. To-do list: `research/sessions/TODO_2026-02-23.md`. **Window result filtering (`penalize_single_line_windows()`):** Three outcomes: (1) matched words span line break → genuine enjambment, kept as 2-line display with cross-break gap penalty `exp(-0.25 × gap)` where gap = tokens between last match on line 1 and first match on line 2; (2) matched words all on one line → trimmed to single-line display (preserves recall without visual clutter); (3) position lookup fails → falls back to `highlight_indices`. Uses `_matched_word_indices()` for position lookup (not `highlight_indices` which include incidental dictionary synonyms). Range refs formatted as abbreviated ranges (e.g., "Vergil, Aeneid 1.469–470"). **Structural fingerprint matching:** `syntax_structural` channel — lines with identical dependency head patterns matched directly (no shared lemmas needed). Weight 0.5 (reduced from 1.5 to suppress false positives from common syntactic patterns). Semantic recovery (`_recover_semantic_for_structural()`) injects cosine similarity for structural pairs filtered by semantic cap. **Memory-aware multiprocessing:** `backend/worker_util.py` caps workers at 4, drops to 2 when available RAM < 16GB, preventing OOM kills. **Next planned work:** DHQ article writing tool (plan at `research/plans/article_writing_plan.md`).

## Research Directory
All research artifacts are in `research/`: plans, session notes, writing (abstracts/articles), references, and dated study results. The latest evaluation report is always at `research/LATEST_REPORT.md`.

## Key Study: Fusion Experiment Phase 1
- **Report:** `research/studies/fusion_experiment_phase1/publication/EVALUATION_REPORT.md`
- **Abstract:** `research/studies/fusion_experiment_phase1/publication/DCA_SCS_2027_ABSTRACT.md`
- **Reproducibility:** `research/studies/fusion_experiment_phase1/publication/REPRODUCIBILITY_GUIDE.md`
- **Data:** `research/studies/fusion_experiment_phase1/data/` (baselines, fusion, Config D CSVs)
- **Article draft:** `docs/ARTICLE_METHODS_DRAFT.md` (V6 development history + Section 14: fusion)
- **Roadmap:** `ROADMAP.md` (full development roadmap with fusion completion)
