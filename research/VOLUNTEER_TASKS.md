# Tesserae V6 — Volunteer Development Tasks

Last updated: 2026-02-25

These tasks extend Tesserae V6's multilingual intertext detection capabilities. The codebase is Flask + React, with SQLite inverted indexes and pre-computed neural embeddings. All code is on GitHub at `tesserae/tesserae-v6` (branch: `main`).

---

## Task 1: Greek and English Syntax Parsing

### Background

Tesserae V6's fusion search uses 9 detection channels. One of these — the **syntax channel** — compares grammatical dependency structures between passages to detect parallel sentence construction even when no vocabulary is shared. Currently, all **1,429 Latin texts** (542,000+ lines) have been parsed using LatinPipe (EvaLatin 2024 winner). Greek (658 texts) and English (13 texts) have **no syntax data**, so the syntax channel contributes nothing for those languages.

### Goal

Build syntax databases for Greek and English so the syntax channel works for all three languages.

### How Latin Syntax Was Built (Reference Implementation)

The Latin pipeline is fully documented in code and can serve as a template:

1. **Parser**: LatinPipe (`latin-evalatin24-240520`), run via REST API or local server
2. **Build script**: `scripts/marvin_latinpipe/build_latinpipe_syntax.py` (780 lines, self-contained)
3. **Process**: Read each `.tess` file → batch lines (20 per request) → send to parser → receive CoNLL-U output → extract tokens, lemmas, UPOS, heads, deprels, feats → store in SQLite
4. **Output**: `syntax_latin.db` (~1.6 GB) with schema:
   - `texts` table: filename → text_id mapping
   - `syntax` table: (text_id, ref) → JSON arrays of tokens, lemmas, upos, heads, deprels, feats
   - `syntax_source` table: parser name, model, build date, counts
5. **Merge**: `scripts/marvin_latinpipe/merge_syntax_index.py` copies parsed data into production index

### How Syntax Scoring Works

In `backend/fusion.py` (lines 370–446):
- Each line is represented as a set of dependency relation patterns (e.g., `nsubj→VERB`, `amod→NOUN`)
- **Shared lemma + same deprel**: score += 1.0
- **Same deprel category** (e.g., nsubj and csubj both "core"): score += 0.7
- **Same POS fallback**: score += 0.4
- **Core argument signature bonus**: +0.5 for matching structural fingerprints (nsubj, obj, csubj overlap)
- Final score normalized to [0, 1]

The dependency relation categories are language-agnostic (Universal Dependencies standard), defined in `backend/syntax_parser.py` lines 13–22:
```
core:         nsubj, obj, iobj, csubj, ccomp, xcomp
non_core:     obl, vocative, expl, dislocated
nominal:      nmod, appos, nummod, amod, acl, det, case
coordination: conj, cc
modifier:     advmod, discourse, aux, cop, mark, advcl
```

### Recommended Approach for Greek

**Option A: Stanza (recommended starting point)**
- Already in `requirements.txt` and integrated in `backend/syntax_parser.py` (`StanzaParser` class, lines 349–492)
- Download model: `stanza.download('grc')` (~29 MB)
- Pipeline: `stanza.Pipeline('grc', processors='tokenize,pos,lemma,depparse')`
- Output: CoNLL-U compatible — same format as LatinPipe
- Speed: ~1–3 lines/sec (CPU). For 658 texts (~200K lines), estimate ~20–55 hours of compute time.

**Option B: Use existing UD treebank data directly**
- `data/treebanks/UD_Ancient_Greek-Perseus/` (13,919 sentences, 203K tokens) — **already in repo**
- `data/treebanks/UD_Ancient_Greek-PROIEL/` — **already in repo**
- These cover Homer, Hesiod, Aeschylus, Sophocles, Herodotus, Plato, NT, etc.
- For texts that match treebank sentences, no parsing needed — direct lookup
- For remaining texts, fall back to Stanza

**Option C: OdyCy / GreekPipe**
- Check LINDAT (lindat.mff.cuni.cz) for Ancient Greek models comparable to LatinPipe
- May offer higher accuracy than Stanza for dependency parsing

### Recommended Approach for English

**Option A: Stanza**
- Download: `stanza.download('en')` (model: `en_ewt`)
- Pipeline: `stanza.Pipeline('en', processors='tokenize,pos,lemma,depparse')`
- Small corpus (13 texts, ~62K lines) — should complete in under an hour

**Option B: spaCy** (`en_core_web_lg`)
- Higher accuracy for modern English
- Requires CoNLL-U format conversion
- Would need to be added to `requirements.txt`

### Concrete Steps

1. **Adapt the build script**: Copy `scripts/marvin_latinpipe/build_latinpipe_syntax.py` and modify to use Stanza instead of LatinPipe. The DB schema stays identical.
2. **Build `syntax_grc.db`**: Run on all 658 Greek texts. Use tmux — this will take many hours.
3. **Build `syntax_en.db`**: Run on all 13 English texts. Should be quick.
4. **Place in production**: Copy to `data/inverted_index/syntax_grc.db` and `syntax_en.db`
5. **Update `fusion.py`**: Modify `_load_syntax_for_text()` to load from language-appropriate DB (currently hardcoded to `syntax_latin.db`)
6. **Test**: Run fusion search on Greek text pairs and verify syntax badges appear in results

### Key Files

| File | Purpose |
|------|---------|
| `scripts/marvin_latinpipe/build_latinpipe_syntax.py` | Latin build script (template) |
| `scripts/build_syntax_index.py` | Language-agnostic Stanza builder (already exists!) |
| `backend/syntax_parser.py` | Core classes: SyntaxToken, SyntaxSentence, StanzaParser |
| `backend/fusion.py` lines 323–581 | Syntax loading, scoring, and channel integration |
| `data/treebanks/UD_Ancient_Greek-*/` | Existing Greek treebank data |

### Acceptance Criteria

- [ ] `syntax_grc.db` exists with parses for all 658 Greek texts
- [ ] `syntax_en.db` exists with parses for all 13 English texts
- [ ] Fusion search on a Greek text pair shows syntax channel badges in results
- [ ] Fusion search on an English text pair shows syntax channel badges in results
- [ ] Regression: Latin "arma virum" search still returns Ovid, Quintilian, Seneca (see `tests/search_reference_tests.md`)

---

## Task 2: Corpus Expansion

### Background

The current corpus has 2,100 texts: 1,429 Latin, 658 Greek, 13 English. Latin and Greek are well-represented for classical antiquity, but there are gaps — particularly in late antique, medieval, and Neo-Latin texts. English is minimal (mostly Shakespeare and a few others). Historical English (Chaucer, KJV, Milton, Pope, Dryden, etc.) is a priority because many of these authors directly translated or imitated classical texts.

### 2a. Add All Available Greek and Latin Corpora

**Sources for additional texts:**
- **Perseus Digital Library** (perseus.tufts.edu): Large collection of Greek and Latin texts in TEI XML. Many are already in the corpus but some may be missing.
- **The Latin Library** (thelatinlibrary.com): Plain-text Latin texts, easy to convert to .tess format.
- **First1KGreek** (github.com/OpenGreekAndLatin/First1KGreek): Open Greek texts from the first millennium, TEI XML.
- **CLTK Corpora** (github.com/cltk): Downloadable Latin and Greek text collections.
- **DigiLibLT** (digiliblt.uniupo.it): Digital Library of Late-Antique Latin Texts — especially valuable for late antique coverage.
- **Musisque Deoque** (mqdq.it): Latin poetry with metrical data.
- **Corpus Corporum** (mlat.uzh.ch/MLS): Medieval Latin texts from Zurich.

**Priority gaps to fill:**
- Late antique Latin (Claudian, Ausonius, Prudentius, Boethius — partial coverage currently)
- Medieval Latin (Dante's Latin works, Petrarch's Latin, goliardic poetry)
- Neo-Latin (More's Utopia, Erasmus, Bacon's Latin works, Milton's Latin poetry)
- Hellenistic/Imperial Greek (Plutarch's complete works, Lucian, Nonnus)
- Patristic Greek (Basil, Gregory of Nazianzus, John Chrysostom)

**Process for adding texts:**
1. Obtain plain text or TEI XML
2. Convert to .tess format: `<author.work book.line> text content` (see Help page's Text Formatter utility)
3. Place in `texts/{la,grc}/`
4. Use admin panel to approve and index, OR run indexing scripts:
   ```bash
   python scripts/build_inverted_index.py --language la --texts texts/la/new_text.tess
   python backend/precompute_embeddings.py --language la --file texts/la/new_text.tess
   python scripts/rebuild_lemma_cache.py --language la --file texts/la/new_text.tess
   ```
5. Rebuild frequency caches for stoplists

**Computational cost per text:** ~5–10 minutes (mostly embedding computation). For bulk additions, batch processing is available via the admin panel or scripts.

### 2b. Expand Historical English

**Priority texts** (direct classical reception):
- Chaucer: Canterbury Tales, Troilus and Criseyde
- KJV Bible (for comparison with Vulgate Latin and LXX Greek)
- Milton: Paradise Lost, Paradise Regained, Samson Agonistes
- Dryden: Translations of Virgil, Ovid, Juvenal
- Pope: Translations of Homer's Iliad and Odyssey
- Chapman: Homer translations
- Marlowe: Hero and Leander, Dido Queen of Carthage
- Jonson: Catiline, Sejanus
- Spenser: Faerie Queene
- Tennyson: Idylls of the King

**Sources:** Project Gutenberg (gutenberg.org), Early English Books Online (EEBO), Oxford Text Archive. Most are out of copyright and freely available.

**Note on English lemmatization:** Currently uses only NLTK WordNetLemmatizer, which is adequate for modern English but may struggle with Early Modern forms (e.g., "hath" → "have", "doth" → "do", "thee/thou/thy"). May need a supplementary lookup table similar to what Latin and Greek have. Historical English stopwords (thou, thee, thy, hath, doth, etc.) are already in the default English stoplist.

### Storage Estimates

| Addition | Texts | Corpus Size | Embeddings | Index |
|----------|-------|-------------|------------|-------|
| +500 Latin | ~50 MB | ~1.5 GB | ~100 MB | ~200 MB |
| +200 Greek | ~25 MB | ~600 MB | ~40 MB | ~80 MB |
| +50 English | ~10 MB | ~150 MB | ~10 MB | ~20 MB |

Current server has ample disk space for these additions.

---

## Task 3: Descendant Language Support (French, Italian, Spanish)

### Background

A major scholarly goal is tracing the influence of classical Latin and Greek on later European literatures. This requires (a) adding corpora in descendant languages and (b) enabling cross-language matching between Latin/Greek and French/Italian/Spanish.

### 3a. Adding a New Language — What's Required

Adding a language (e.g., Old French, `fro`) requires changes in **7+ files**. The current language list `['la', 'grc', 'en']` is hardcoded throughout the codebase:

**Backend changes:**
1. `backend/text_processor.py` — Add tokenization + lemmatization functions for the new language
2. `backend/app.py` — Add language to corpus loops, frequency caches, text listing
3. `backend/utils.py` — Add to language validation
4. `backend/matcher.py` — Add normalization function and stoplist defaults
5. `backend/semantic_similarity.py` — Add model selection for new language
6. `backend/inverted_index.py` — Add to indexing loops
7. `backend/bigram_frequency.py` — Add to frequency computation

**Frontend changes:**
8. `client/src/App.jsx` — Add language tab
9. `client/src/data/stoplists.js` — Add default stoplist for new language
10. `client/src/utils/formatting.js` — Add display name and reference formatting

**Data requirements:**
11. `texts/{lang}/` — Directory with .tess files
12. `data/lemma_tables/{lang}_lemmas.json` — Lemma lookup table (from UD treebank)
13. UD treebank in `data/treebanks/UD_{Language}-{Treebank}/` — For building lemma tables
14. Semantic embeddings model — Choose or train appropriate model

**Infrastructure suggestion:** Refactor the hardcoded language lists into a single configuration file (e.g., `backend/languages.py`) that all modules import. This would make adding new languages a config change rather than a multi-file edit. This is a good standalone volunteer task.

### 3b. Candidate Languages and Resources

| Language | Code | UD Treebanks | Lemmatizer | Semantic Model | Corpus Sources |
|----------|------|-------------|------------|----------------|----------------|
| Old French | `fro` | UD_Old_French-SRCMF | Stanza/CLTK | mBERT, CamemBERT | BFM, SRCMF |
| Middle French | `frm` | Limited | Stanza | CamemBERT | Frantext |
| Old Italian | `it_old` | UD_Italian_Old-ISDT (partial) | Stanza | Italian BERT | OVI, Biblioteca Italiana |
| Old Spanish | `osp` | UD_Old_Spanish-GSD (planned) | Stanza | BETO | Hispanic Seminary |
| Medieval Latin | `la_med` | Can reuse UD_Latin-* | Same as Latin | SPhilBERTa | Corpus Corporum, ALIM |

**UD Treebank availability** (universaldependencies.org):
- **Old French (SRCMF)**: 17,678 sentences, 170K tokens — excellent coverage
- **Italian (ISDT)**: 14,167 sentences — modern, but usable as a starting point
- **Spanish (GSD/AnCora)**: Multiple treebanks available for modern Spanish
- **Note**: Old/medieval variants of Romance languages have less NLP tooling than modern forms. Modern tools (spaCy, Stanza) can be fine-tuned on historical data.

**Priority corpora for each language:**

**Old French / Middle French:**
- Chanson de Roland (direct Virgilian echoes)
- Roman d'Eneas (adaptation of Aeneid)
- Roman de Troie (Benoit de Sainte-Maure)
- Ovide moralisé (medieval Ovid adaptation)
- Chrétien de Troyes (Arthurian romances with classical allusions)

**Old/Early Italian:**
- Dante: Divina Commedia, De Monarchia (Latin), De Vulgari Eloquentia
- Petrarch: Canzoniere, Africa (Latin epic on Scipio)
- Boccaccio: Genealogia Deorum, Teseida

**Old/Early Spanish:**
- Libro de Alexandre (Alexander the Great)
- General Estoria (Alfonso X — draws on Ovid, Lucan)
- La Celestina (Rojas)
- Garcilaso de la Vega (Renaissance, heavy Virgilian influence)

### 3c. Cross-Language Matching (Classical → Descendant)

This is the high-value scholarly goal: detecting how classical texts influenced later literatures across language boundaries.

**Current infrastructure:**
- Latin↔Greek cross-lingual matching already works via SPhilBERTa (trained on parallel classical texts) and a curated dictionary (34,535 pairs)
- The same architecture (`backend/semantic_similarity.py`, `backend/synonym_dict.py`) can be extended

**Approaches for Latin→Romance matching:**

1. **Multilingual embeddings (quickest path)**
   - Use **XLM-RoBERTa** or **mBERT** — pre-trained on 100+ languages including Latin, French, Italian, Spanish
   - These models place semantically similar sentences from different languages near each other in embedding space
   - Would replace SPhilBERTa for cross-lingual pairs involving Romance languages
   - Trade-off: Less specialized for classical texts than SPhilBERTa, but broadly multilingual

2. **Cognate/etymology dictionary**
   - Build CSV files analogous to `greek_latin_dict.csv` mapping Latin lemmata to Romance descendants
   - Resources: Wiktionary etymological data, REW (Romanisches Etymologisches Wörterbuch), FEW (French)
   - The existing cognate transliteration approach (`backend/synonym_dict.py`) could be adapted — Latin→Italian cognates are even more regular than Greek→Latin

3. **Fine-tuned model (highest quality, most effort)**
   - Fine-tune XLM-R or similar on parallel Latin-Romance text pairs
   - Training data: Dryden's Virgil (English↔Latin), Roman d'Eneas (French↔Latin), etc.
   - Would give the best results but requires ML expertise and GPU compute

**Frontend changes needed:**
- Extend the cross-lingual tab to support language pair selection beyond just Greek↔Latin
- Add dropdown for source and target language independently
- Display results with appropriate bilingual highlighting

### Computational Limits

**Current server (Marvin):**
- Disk: Ample for several thousand additional texts
- RAM: Embedding computation (~2 GB per model loaded) — manageable
- CPU: Stanza/spaCy parsing is CPU-bound. For bulk corpus parsing (thousands of texts), expect days of compute time. Use tmux.
- GPU: Not available on Marvin. Embedding computation and parsing are slower but functional on CPU.

**Bottlenecks:**
- Embedding computation: ~5–10 min per text on CPU. For 500 new texts, ~40–80 hours.
- Index building: Fast (~1 min per text)
- Syntax parsing: ~1–3 lines/sec with Stanza. For 200K lines of Greek, ~20–55 hours.

**Recommendation:** Batch processing with checkpoint/resume is essential. The existing scripts (`batch_lemma_cache.py`, `build_latinpipe_syntax.py`) already support this pattern.

---

## Task 4: Language Configuration Refactoring

### Background

Adding a new language currently requires editing 7+ files to add the language code to hardcoded lists. This is error-prone and should be centralized.

### Goal

Create a single language configuration module that all backend and frontend code references.

### Proposed Design

**`backend/languages.py`:**
```python
LANGUAGES = {
    'la': {
        'name': 'Latin',
        'display_name': 'Latin',
        'lemma_table': 'latin_lemmas.json',
        'embedding_model': 'bowphs/SPhilBerta',
        'tokenizer': 'tokenize_latin',
        'lemmatizer': '_latin_lemmatize',
        'stoplist_size': 66,
        'has_syntax': True,
    },
    'grc': { ... },
    'en': { ... },
}

CROSS_LINGUAL_PAIRS = [
    ('la', 'grc', 'bowphs/SPhilBerta', 'greek_latin_dict.csv'),
]
```

**Changes required:**
1. Create `backend/languages.py` with the config dict
2. Replace all hardcoded `['la', 'grc', 'en']` loops with `LANGUAGES.keys()`
3. Create `client/src/config/languages.js` (or serve from API endpoint `/api/languages`)
4. Replace frontend hardcoded language tabs with dynamic rendering from config

### Acceptance Criteria

- [ ] Adding a new language requires editing only `backend/languages.py` (and providing data files)
- [ ] All existing functionality unchanged
- [ ] Regression tests pass

---

## Getting Started

### Setup

1. Clone the repo: `git clone https://github.com/tesserae/tesserae-v6.git`
2. Create venv: `python -m venv venv && source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and configure database connection
5. Download data files (indexes, embeddings) — see `scripts/download_data.py`

### Running the Dev Server

```bash
source venv/bin/activate
export $(grep -v '^#' .env | xargs)
export TESSERAE_DIRECT_SERVER=1
python -c "from backend.app import app, start_cache_init; start_cache_init(); app.run(host='0.0.0.0', port=8080)"
```

### Testing on Marvin (port 5000)

```bash
ssh -L 5000:localhost:5000 <username>@marvin.caset.buffalo.edu
```
Then open http://localhost:5000

### Regression Tests

Before submitting any PR that touches search, indexing, or text processing:
- Run tests in `tests/search_reference_tests.md`
- The "arma virum" lemma search must return Ovid, Quintilian, Seneca
- Verify fusion search still completes on Aeneid Book 1 × Bellum Civile Book 1

### Key Documentation

- `CLAUDE.md` — Project architecture and conventions
- `docs/CONTRIBUTING.md` — Contribution guidelines
- `docs/PR_REVIEW_PROCEDURE.md` — PR review process
- Help & Support page (in the running app) — End-user documentation
