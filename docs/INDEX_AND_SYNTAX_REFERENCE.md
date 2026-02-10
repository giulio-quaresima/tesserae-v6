# Inverted Index & Syntax Database Reference

**Last Updated:** February 10, 2026

---

## Inverted Indexes

Pre-built SQLite databases for fast corpus-wide lemma searches. Maps lemma → list of (text_id, line_ref, positions) for instant lookups.

### Current Status (Feb 10, 2026 — Fully Rebuilt)

| Language | Texts | Lines | Unique Lemmas | Index Size | Build Method |
|----------|-------|-------|---------------|------------|-------------|
| Latin | 1,429 | 865,842 | 298,757 | 2.2 GB | LatinPipe (64%) + CLTK/UD fallback (36%) |
| Greek | 659 | ~270,000 | 360,429 | 1.4 GB | UD table (58K entries), `--fast` mode |
| English | 14 | ~62,000 | 22,867 | 79 MB | NLTK WordNet |

### File Locations

Same relative paths on Replit and Marvin:
```
data/inverted_index/la_index.db    # Latin
data/inverted_index/grc_index.db   # Greek
data/inverted_index/en_index.db    # English
data/inverted_index/syntax_latin.db  # Latin syntax parses (separate)
```

### Database Schema

```sql
-- Which texts are indexed
CREATE TABLE texts (
    text_id INTEGER PRIMARY KEY,
    filename TEXT UNIQUE,
    author TEXT,
    title TEXT,
    line_count INTEGER
);

-- Lemma → location mappings (core of the inverted index)
CREATE TABLE postings (
    lemma TEXT,
    text_id INTEGER,
    ref TEXT,
    positions TEXT  -- JSON array of token positions
);

-- Full line content for displaying results
CREATE TABLE lines (
    text_id INTEGER,
    ref TEXT,
    content TEXT,     -- Original text
    lemmas TEXT,      -- JSON array
    tokens TEXT,      -- JSON array
    PRIMARY KEY (text_id, ref)
);
```

### Build Commands

```bash
# Latin — best quality (LatinPipe syntax DB + CLTK fallback)
python3 scripts/build_inverted_index.py -l la --use-syntax-db --force

# Greek — fast mode (UD table only, bypasses slow CLTK Greek lemmatizer)
python3 scripts/build_inverted_index.py -l grc --fast --force

# English — standard (NLTK WordNet)
python3 scripts/build_inverted_index.py -l en --force

# Resume an interrupted build (no --force)
python3 scripts/build_inverted_index.py -l la
```

### Lemmatization Stack

| Language | Primary Lemmatizer | Supplement | Best Available |
|----------|-------------------|------------|----------------|
| Latin | CLTK LatinBackoffLemmatizer | UD table (62K entries) | LatinPipe syntax DB (542K lines, ~90-95% accuracy) |
| Greek | UD table only (fast mode) | 58K entries from UD treebanks | No syntax DB yet |
| English | NLTK WordNetLemmatizer | N/A (WordNet coverage is excellent) | N/A |

### Query-Time Safety Net

A reverse lemma lookup table (lemma → all known inflected forms) runs at query time as a fallback. It expands each query lemma to all known forms and searches for all of them. This catches any remaining lemmatization gaps in the index. Negligible performance overhead.

---

## Syntax Database (Latin)

Pre-computed UD dependency parses for the full Latin corpus, built with LatinPipe (EvaLatin 2024 winner).

### Current Status

- **syntax_latin.db**: 1.6 GB, 1,429 texts, 542,311 lines
- **Parser**: LatinPipe (evalatin24-240520 model, ~90-95% LAS)
- **Built**: February 7, 2026 on Marvin (~16 hours with watchdog auto-recovery)

### Schema

```sql
CREATE TABLE texts (
    text_id INTEGER PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL
);

CREATE TABLE syntax (
    text_id INTEGER NOT NULL,
    ref TEXT NOT NULL,         -- e.g., "verg. aen. 1.1"
    tokens TEXT,               -- JSON array of word forms
    lemmas TEXT,               -- JSON array of lemmas
    upos TEXT,                 -- JSON array of Universal POS tags
    heads TEXT,                -- JSON array of dependency head indices
    deprels TEXT,              -- JSON array of dependency relation labels
    feats TEXT,                -- JSON array of morphological features
    PRIMARY KEY (text_id, ref)
);
```

### Known Quirks

- Enclitic "-que" sometimes confuses the lemmatizer (e.g., "virumque" → "virumqis")
- Enjambed lines parsed independently — accuracy may be slightly lower for incomplete clauses
- Prose texts: .tess "lines" are editor-defined chunks, usually sentence-like, so parsing quality is generally good

### Key Code

- `backend/syntax_parser.py` — `SyntaxMatcher`, `compute_syntax_similarity()`, `get_syntax_for_line()`
- `backend/feature_extractor.py` — `calculate_syntax_score()` (integration point)
- `scripts/marvin_latinpipe/build_latinpipe_syntax.py` — Build script (runs on Marvin only)

### Future: Greek & English Syntax

| Language | Parser | Corpus | Status |
|----------|--------|--------|--------|
| Greek | Stanza UD (~79% LAS) | 659 texts | Planned |
| English | Stanza/spaCy (92-95% LAS) | 14 texts | Planned |

---

## Reference Tests

After any index rebuild or search code changes, verify with these tests:

### Test 1: "arma virum" (Lemma Search)
```bash
curl -s -X POST "http://localhost:5000/api/line-search" \
  -H "Content-Type: application/json" \
  -d '{"query": "arma virum", "language": "la", "search_type": "lemma", "max_results": 500}'
```
**Expected**: 250+ results including Ovid (~26), Vergil (~2), Livy (~72), Cicero (~8)

### Test 2: "arma virum" (Exact Search)
```bash
curl -s -X POST "http://localhost:5000/api/line-search" \
  -H "Content-Type: application/json" \
  -d '{"query": "arma virum", "language": "la", "search_type": "exact", "max_results": 200}'
```
**Expected**: 35-40+ results including Ovid, Quintilian, Seneca, Vergil, Statius

### Test 3: Neil Bernstein Clausula Case
```bash
curl -s -X POST "http://localhost:5000/api/line-search" \
  -H "Content-Type: application/json" \
  -d '{"query": "vertice crinis", "language": "la", "search_type": "lemma", "max_results": 100}'
```
**Expected**: Must include Catullus 64.350 ("Cum in cinerem canos soluent a uertice crines")

### Index Health Check
```bash
python3 -c "
import sqlite3
for lang in ['la', 'grc', 'en']:
    db = f'data/inverted_index/{lang}_index.db'
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM texts')
    texts = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM lines')
    lines = c.fetchone()[0]
    c.execute('SELECT COUNT(DISTINCT lemma) FROM postings')
    lemmas = c.fetchone()[0]
    print(f'{lang}: {texts} texts, {lines:,} lines, {lemmas:,} lemmas')
    conn.close()
"
```

---

## Build History

| Date | Action | Details |
|------|--------|---------|
| Jan 25, 2026 | Initial build (Replit) | OOM crash at ~920 Latin texts. Greek partial (514/659). |
| Feb 7, 2026 | LatinPipe syntax build (Marvin) | Full Latin corpus parsed: 542K lines, 1.6GB |
| Feb 9, 2026 | Latin index rebuild (Marvin) | 1,429 texts with --use-syntax-db: 64% LatinPipe, 36% CLTK+UD |
| Feb 9, 2026 | UD lemma table expansion | Latin: 39K → 62K entries (6 treebanks + LatinPipe data) |
| Feb 10, 2026 | Greek index rebuild (Marvin) | 659 texts with --fast mode (UD table only, ~10 min) |
| Feb 10, 2026 | English index rebuild (Marvin) | 14 texts, standard NLTK build |
| Feb 10, 2026 | All indexes synced to Replit | Via Google Drive transfer |
