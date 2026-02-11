# Next Steps: Syntax Index Integration

**Created:** February 7, 2026
**Status:** Ready for implementation after syntax_latin.db is copied to Replit

---

## Current State

- **syntax_latin.db**: 1.6GB, 1,429 texts, 542,311 lines fully parsed
- **Location on Marvin**: `/var/www/tesseraev6_flask/data/inverted_index/syntax_latin.db`
- **Target on Replit**: `data/inverted_index/syntax_latin.db`
- **Parser**: LatinPipe (EvaLatin 2024 winner, ~90-95% LAS)

### Database Schema

```
Table: texts (1,429 rows)
  - text_id INTEGER PRIMARY KEY
  - filename TEXT NOT NULL

Table: syntax (542,311 rows)
  - text_id INTEGER NOT NULL (PK1)
  - ref TEXT NOT NULL (PK2) — e.g., "verg. aen. 1.1"
  - tokens TEXT — JSON array of word forms
  - lemmas TEXT — JSON array of lemmas
  - upos TEXT — JSON array of Universal POS tags
  - heads TEXT — JSON array of dependency head indices
  - deprels TEXT — JSON array of dependency relation labels
  - feats TEXT — JSON array of morphological features

Table: syntax_source (metadata, currently empty — populate after verification)
  - parser TEXT DEFAULT 'latinpipe'
  - model TEXT DEFAULT 'evalatin24-240520'
  - build_date TEXT
  - total_texts INTEGER
  - total_lines INTEGER
```

### Sample Data (Aeneid 1.1)

```
Ref: verg. aen. 1.1
  Tokens: ["Arma", "virumque", "cano", ",", "Troiae", "qui", "primus", "ab", "oris"]
  Lemmas: ["armum", "virumqis", "cano", ",", "troia", "qui", "primus", "ab", "ora"]
  UPOS:   ["NOUN", "NOUN", "VERB", "PUNCT", "PROPN", "PRON", "ADJ", "ADP", "NOUN"]
  Deprels: ["obj", "amod", "root", "punct", "nmod", "nsubj", "amod", "case", "obl"]
```

### Known Quirks

- Enclitic "-que" sometimes confuses the lemmatizer (e.g., "virumque" → "virumqis" instead of "vir")
- Enjambed lines parsed independently — accuracy may be slightly lower for lines that are incomplete clauses
- Prose texts: .tess "lines" are editor-defined chunks, usually sentence-like, so parsing quality is generally good

---

## Step 1: Transfer to Replit

The file is 1.6GB — too large for direct transfer. Options:

### Option A: Compress and transfer via scp/rsync
```bash
# On Marvin:
gzip -k /var/www/tesseraev6_flask/data/inverted_index/syntax_latin.db
# Result: syntax_latin.db.gz (likely ~400-600MB)
# Transfer to Replit via scp or download link
```

### Option B: Make available on Downloads page
- Host the .gz on Marvin's web server as a static file
- Add download link to Tesserae Downloads page
- Users and Replit can both fetch from there

### Option C: Incremental approach
- Start with a subset (e.g., major canonical authors only) for initial testing
- Use full database once transfer method is confirmed

---

## Step 2: Wire into SyntaxMatcher

**File:** `backend/syntax_parser.py`

The existing SyntaxMatcher class needs to:
1. Load syntax_latin.db at startup (read-only connection)
2. Look up syntax data by text filename + line reference
3. Provide methods for comparing syntactic structures between two lines

### Key integration points:
- `get_syntax(text_id, ref)` → returns tokens, lemmas, upos, heads, deprels, feats
- `compare_syntax(line1_data, line2_data)` → returns similarity score
- `find_syntactic_pattern(pattern)` → corpus-wide pattern search

### Matching approaches to implement:
1. **Dependency relation overlap**: Count shared deprel labels (obj, nsubj, obl, etc.)
2. **Subtree matching**: Find shared dependency subtree structures
3. **Syntactic role alignment**: Do matched lemmas play the same grammatical role?
4. **Word order similarity**: Compare position of matched terms relative to their head

---

## Step 3: Enable Syntax-Aware Scoring

Add syntax as a scoring boost (like bigram frequency boost):

```python
# In scoring pipeline:
if syntax_boost_enabled and syntax_data_available:
    syntax_similarity = compare_syntax(source_line, target_line)
    score *= (1 + syntax_weight * syntax_similarity)
```

### UI changes needed:
- Add "Syntax Boost" toggle in Advanced Settings
- Show syntactic annotation on hover/click in results
- Display dependency tree visualization (optional, later phase)

---

## Step 4: Populate syntax_source Metadata

```sql
INSERT INTO syntax_source (parser, model, build_date, total_texts, total_lines)
VALUES ('latinpipe', 'evalatin24-240520', '2026-02-07', 1429, 542311);
```

---

## Step 5: Update Text Ingestion Pipeline

When new Latin texts are approved via admin panel:
1. Send text to LatinPipe REST API (running on Marvin) for parsing
2. Insert results into syntax_latin.db
3. This requires LatinPipe server to be running — or batch new texts periodically

---

## Step 6: Public Distribution

- Add syntax_latin.db.gz to Downloads page
- Consider GitHub Releases for versioned distribution
- Consider Zenodo DOI for scholarly citation
- Document schema and usage in a README

---

## Step 7: Greek and English Syntax Parsing

After Latin integration is complete:

| Language | Parser | Corpus Size | Estimated Time | Output |
|----------|--------|-------------|----------------|--------|
| Greek | Stanza UD | ~310 texts | Several hours | syntax_greek.db |
| English | Stanza/spaCy | ~14 texts | Under 1 hour | syntax_english.db |

These can run on Marvin or Replit (Stanza is much lighter than LatinPipe).

---

## Step 8: Benchmark Testing

Test syntax-enhanced matching against the three scholarly benchmarks:
- Lucan BC1 vs. Aeneid (Coffee et al. 2012)
- Valerius Flaccus Arg 1 (Manjavacas et al. 2019)
- Statius Achilleid (Geneva 2015)

Key question: How many of the ~15% "structural" missed parallels are recovered with syntax matching enabled?

---

## Cleanup (After Everything Works)

On Marvin:
- Remove LatinPipe model (~2GB) from `~/latinpipe_indexing/` if no longer needed
- Keep build script and virtualenv for future re-indexing
- Keep syntax_latin.db in production location
