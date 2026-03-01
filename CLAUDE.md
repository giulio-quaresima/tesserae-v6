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
Fusion search is live on the dev website. Production fusion: **91.0% recall** across 5 benchmarks (784/862). Lucan-Vergil: 92.0% (196/213), Achilleid-Thebaid: 96.2% (50/52) — both surpass Phase 2. Key improvements: restored syntax channel (DB-backed), dictionary on windows, channel optimizations (dictionary inverted-index 850x, lemma_min1 IDF pre-filter 20x, syntax caching+multiprocessing). **Pair-size gates removed** -- all 9 channels run unconditionally on every text pair. Aeneid x Metamorphoses completes in ~12 min with all channels. Progressive SSE streaming with "Pause updates" button. **Config K -- Three-layer rarity scoring + single-word penalty** (current): Uses geometric mean corpus-IDF (1,429 Latin texts) as the basis for three distinct rarity effects: (1) **squared base multiplier** -- common-word pairs have base scores reduced by up to 96%; (2) **squared IDF-weighted convergence** -- convergence bonus weighted by `min(1.0, geom_idf)^2`, eliminating convergence credit for common-word pairs; (3) **convergence-scaled rarity boost** -- pairs sharing rare words across multiple detection methods get an additive boost scaled by `min(channel_factor, word_factor)` where `channel_factor=(n_channels-1)/5` and `word_factor=(n_unique_words-1)/3` (weight=0.5, cap=2.0). **Single-word penalty** (commit `3f16a0b`): `SINGLE_WORD_PENALTY=0.5` applied to rarity multiplier when `n_unique_words <= 1`, before Layer 1 squaring -- effective 75% score reduction (0.5^2=0.25) for single rare-word matches; multi-word allusions unaffected. Earlier fixes (commit `6732e0a`): (A) idf=0 lexical entries included in rarity; (B) surface form deduplication; (C) word-count factor for Layer 3 boost. IDF floor=0.2, threshold=1.5. Channel weights: ed=2.0, sn=4.0, ex=1.0, lm=2.0, rw=2.0, dc=0.5, se=1.2, sy=0.3, m1=0.3. Convergence bonus=0.75. Total recall: 784/862 (91.0%, unchanged). Study report: `research/studies/2026-02-27_weight_optimization/REPORT.md`. To-do list: `research/sessions/TODO_2026-02-23.md`.

## Research Directory
All research artifacts are in `research/`: plans, session notes, writing (abstracts/articles), references, and dated study results. The latest evaluation report is always at `research/LATEST_REPORT.md`.

## Key Study: Fusion Experiment Phase 1
- **Report:** `research/studies/fusion_experiment_phase1/publication/EVALUATION_REPORT.md`
- **Abstract:** `research/studies/fusion_experiment_phase1/publication/DCA_SCS_2027_ABSTRACT.md`
- **Reproducibility:** `research/studies/fusion_experiment_phase1/publication/REPRODUCIBILITY_GUIDE.md`
- **Data:** `research/studies/fusion_experiment_phase1/data/` (baselines, fusion, Config D CSVs)
- **Article draft:** `docs/ARTICLE_METHODS_DRAFT.md` (V6 development history + Section 14: fusion)
- **Roadmap:** `ROADMAP.md` (full development roadmap with fusion completion)
