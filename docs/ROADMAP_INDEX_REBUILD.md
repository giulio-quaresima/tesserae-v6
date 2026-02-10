# Roadmap: Full Index Rebuild for Permanent Lemmatization

**Created:** February 9, 2026
**Last Updated:** February 9, 2026 (evening)
**Status:** IN PROGRESS — Latin complete, Greek running overnight, English pending

---

## Context: Why a Full Rebuild Is Needed

### The Current Situation

Tesserae V6 uses an **inverted index** (a pre-built database) for fast corpus-wide searches. When a user searches for "arma virum," the system looks up which lines contain those lemmas in the index, rather than scanning every text file.

The index was originally built in January 2026 using **CLTK** (Classical Language Toolkit) as the lemmatizer. CLTK is the standard Latin/Greek lemmatizer, but it has gaps — many inflected forms get stored in the index as-is rather than being mapped to their proper dictionary headwords. For example:

| Inflected Form | CLTK Returns | Correct Lemma |
|----------------|-------------|---------------|
| crines         | crines ❌    | crinis ✓     |
| uertice        | uertice ❌   | uertex ✓     |
| crinibus       | crinibus ❌  | crinis ✓     |

### The Workaround (Still Active as Safety Net)

In February 2026, we built a **query-time fallback system**:
1. Expanded the lemma lookup table from 39K to 62K entries using 6 UD treebanks + LatinPipe data
2. Built a reverse lookup table (lemma → all known inflected forms)
3. At query time, the system expands each query lemma to all its known inflected forms and searches for ALL of them in the index

This works — both reference tests pass. It remains in place as a safety net even after the rebuild.

### The Permanent Fix

Rebuild all three indexes (Latin, Greek, English) from scratch using the improved lemmatization. After rebuilding:
- Every word in the index will be stored under its correct dictionary headword
- The query-time fallback system becomes unnecessary (but harmless to keep as a safety net)
- Search accuracy improves for all queries, not just the ones we've tested

---

## Current Rebuild Status (Feb 9, 2026 evening)

| Language | Status | Texts | Lines | Unique Lemmas | Postings | Index Size |
|----------|--------|-------|-------|---------------|----------|------------|
| Latin    | **COMPLETE** ✓ | 1,429 | 865,842 | 298,757 | 17,681,642 | 2.2 GB |
| Greek    | **RUNNING** (overnight) | 659 | TBD | TBD | TBD | Growing (~7MB so far) |
| English  | **PENDING** | 14 | TBD | TBD | TBD | ~5 min build |

### Latin Build Details
- Built with `--use-syntax-db --force` on Marvin
- LatinPipe syntax hits: 553,340 lines (64%) — best quality lemmatization
- Fallback to CLTK + UD table: 312,502 lines (36%)
- CLTK installed on Marvin via `pip install --user --break-system-packages cltk`
- Latin and Greek CLTK model data downloaded to `~/cltk_data/`
- POS tagging errors (non-fatal, see Known Issues below) present on fallback lines

### Greek Build Details
- Running overnight with `--force` on Marvin
- No syntax database for Greek — all lines use CLTK + 58K-entry UD table
- Slower than Latin because every line goes through CLTK's live lemmatizer
- Expected completion: several hours

---

## Lemmatization Stack Per Language

**Latin (la):**
- Primary: CLTK `LatinBackoffLemmatizer` — rule-based with backoff strategies
- Supplement: UD lemma table (`data/lemma_tables/latin_lemmas.json`, 62K entries from 6 treebanks + LatinPipe)
- Best available: LatinPipe syntax database (`syntax_latin.db`, 542K lines, ~90-95% accuracy) — used during rebuild via `--use-syntax-db` flag
- Reverse lookup: ✓ Built at runtime from UD table

**Greek (grc):**
- Primary: CLTK `GreekBackoffLemmatizer`
- Supplement: UD lemma table (`data/lemma_tables/greek_lemmas.json`, 58K entries)
- No syntax database equivalent to LatinPipe exists yet
- Reverse lookup: ✓ Built at runtime from UD table

**English (en):**
- Primary: NLTK `WordNetLemmatizer`
- No supplementary table (WordNet coverage is very good for English)
- Only 14 texts — small corpus, fast to rebuild
- Reverse lookup: Not applicable (not needed)

**Important:** The improved lemma tables benefit ALL features, not just the inverted index. Any feature that lemmatizes text on the fly (two-text search, line search, stoplists, semantic matching, rare word search) already uses the expanded UD tables at runtime.

---

## What To Do Next (When You Pick Up)

### Step 1: Check Greek Build Results

On Marvin, the Greek build should have finished overnight. Check the terminal for the completion summary:
```
  Completed: 659 texts, XXXXX lines, XXXXX unique lemmas, XXXXX postings
  Index size: XXX.X MB
```

### Step 2: Run English Build

```bash
cd /var/www/tesseraev6_flask/
git pull origin main
python3 scripts/build_inverted_index.py -l en --force
```
Takes under 5 minutes.

### Step 3: Verify on Marvin

Test the rebuilt indexes directly on Marvin:
```bash
# Test 1: arma virum (must include Ovid, Quintilian, Seneca)
curl -s -X POST "http://localhost:5000/api/line-search" \
  -H "Content-Type: application/json" \
  -d '{"query": "arma virum", "language": "la", "search_type": "lemma", "max_results": 500}'

# Test 2: vertice crinis (must include Catullus 64.350)
curl -s -X POST "http://localhost:5000/api/line-search" \
  -H "Content-Type: application/json" \
  -d '{"query": "vertice crinis", "language": "la", "search_type": "lemma", "max_results": 100}'
```

### Step 4: Copy Rebuilt Indexes to Replit

```bash
# From Marvin, SCP to local machine, then upload to Replit:
scp marvin:/var/www/tesseraev6_flask/data/inverted_index/la_index.db .
scp marvin:/var/www/tesseraev6_flask/data/inverted_index/grc_index.db .
scp marvin:/var/www/tesseraev6_flask/data/inverted_index/en_index.db .
# Upload via Replit Files panel (drag into data/inverted_index/)
```

### Step 5: Verify on Replit

Run the same reference tests on Replit after uploading.

### Step 6: Post-Rebuild Cleanup

1. Update `replit.md` to note indexes are rebuilt
2. Consider re-running evaluation benchmark to measure precision/recall improvement
3. Delete old backup index files on Marvin when confident

---

## Build Commands Reference

```bash
# Latin — best quality (LatinPipe + CLTK fallback)
python3 scripts/build_inverted_index.py -l la --use-syntax-db --force

# Greek — CLTK + UD table
python3 scripts/build_inverted_index.py -l grc --force

# English — NLTK WordNet
python3 scripts/build_inverted_index.py -l en --force

# All languages at once
python3 scripts/build_inverted_index.py --force

# Resume interrupted build (no --force)
python3 scripts/build_inverted_index.py -l la
```

---

## Code Changes Made (Feb 9)

### 1. Added `--force` and `--use-syntax-db` Flags ✓
- `scripts/build_inverted_index.py` now accepts both flags
- `--force` deletes existing index file and rebuilds from scratch
- `--use-syntax-db` loads LatinPipe syntax database for Latin lemmatization

### 2. Fixed Syntax Database Loader ✓
- Fixed key format: uses `(filename, ref)` matching the syntax DB's `texts` table
- Fixed column name: `ref` not `locus`

### 3. Fixed POS Tagger Input Format ✓
- CLTK's `tag_tnt` expects a string, not a list — now joins tokens before passing
- Added `RecursionError` handling (Greek tagger hits recursion limit on complex sentences)
- Suppressed repeated error messages to avoid terminal spam

---

## Known Issues

### POS Tagging Errors (Non-Fatal)
- **Latin:** CLTK's `tag_tnt` occasionally fails with input format issues. Fixed in latest code but the Latin build ran before the fix was deployed.
- **Greek:** CLTK's Greek TnT tagger hits maximum recursion depth on some sentences. Fixed in latest code (silently caught).
- **Impact:** Minimal. POS tagging only helps CLTK disambiguate between lemma candidates. When POS tagging fails, CLTK still lemmatizes without POS information. The UD table handles most disambiguation cases anyway.

### CLTK Installation on Marvin
- Installed via `python3 get-pip.py --user --break-system-packages` then `pip install --user --break-system-packages cltk`
- CLTK model data in `/home/ncoffee/cltk_data/` (Latin and Greek models)
- NLTK also installed as a CLTK dependency

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| Feb 9, 2026 | Expand Latin lemma table to 62K entries | CLTK alone missed ~37% of forms in Neil Bernstein test case |
| Feb 9, 2026 | Build query-time reverse lookup as interim fix | Full index rebuild requires Marvin; this gives immediate improvement |
| Feb 9, 2026 | Fix distance filter to use min pairwise distance | Old span-based calculation falsely rejected prose matches with repeated words |
| Feb 9, 2026 | Plan full index rebuild on Marvin | Query-time workaround is effective but a proper rebuild is the permanent solution |
| Feb 9, 2026 | Use LatinPipe for Latin rebuild | 542K lines at ~90-95% accuracy vs CLTK's lower accuracy |
| Feb 9, 2026 | Install CLTK on Marvin for fallback quality | 312K Latin lines (36%) not in LatinPipe DB need good fallback |
| Feb 9, 2026 | Keep query-time fallback as safety net | Negligible overhead, catches any remaining gaps after rebuild |
