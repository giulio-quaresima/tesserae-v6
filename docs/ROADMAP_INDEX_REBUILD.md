# Roadmap: Full Index Rebuild for Permanent Lemmatization

**Created:** February 9, 2026
**Status:** Planning — ready for next work session

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

### The Workaround (Current State)

In February 2026, we built a **query-time fallback system**:
1. Expanded the lemma lookup table from 39K to 62K entries using 6 UD treebanks + LatinPipe data
2. Built a reverse lookup table (lemma → all known inflected forms)
3. At query time, the system expands each query lemma to all its known inflected forms and searches for ALL of them in the index

This works — both reference tests pass (arma virum returns Ovid/Quintilian/Seneca; vertice crinis returns Catullus 64.350). But it's a workaround:
- Extra query-time computation (expanding forms, larger SQL queries)
- Can't find forms that aren't in the UD table
- The index itself still stores incorrect lemmas, making it fragile

### The Permanent Fix

Rebuild all three indexes (Latin, Greek, English) from scratch using the improved lemmatization. After rebuilding:
- Every word in the index will be stored under its correct dictionary headword
- The query-time fallback system becomes unnecessary (but harmless to keep as a safety net)
- Search accuracy improves for all queries, not just the ones we've tested

---

## Current Index Status

| Language | Text Files | Index Size | Index Complete? | Lemmatizer | Lemma Table |
|----------|-----------|------------|-----------------|------------|-------------|
| Latin    | 1,429     | 2.1 GB     | Partial (built Jan 25, OOM crash mid-build) | CLTK + UD table (62K entries) | ✓ Expanded Feb 9 |
| Greek    | 659       | 1.5 GB     | Partial (~77%) | CLTK + UD table (58K entries) | ✓ Exists |
| English  | 14        | 80 MB      | Complete        | NLTK WordNet | No separate table needed |

### Lemmatization Stack Per Language

**Latin (la):**
- Primary: CLTK `LatinBackoffLemmatizer` — rule-based with backoff strategies
- Supplement: UD lemma table (`data/lemma_tables/latin_lemmas.json`, 62K entries from 6 treebanks + LatinPipe)
- Best available: LatinPipe syntax database (`syntax_latin.db`, 542K lines, ~90-95% accuracy) — can be used during rebuild via `--use-syntax-db` flag
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

---

## Rebuild Plan

### Prerequisites

1. **Push latest code to Git** — The build script, expanded lemma tables, and all fixes must be on `main`
2. **SSH access to Marvin** — The rebuild must run on Marvin (Replit runs out of memory for the full Latin corpus)
3. **Back up existing indexes** before starting

### Step 1: Latin Index Rebuild (Priority — Largest Corpus)

**On Marvin:**
```bash
ssh marvin
cd /var/www/tesseraev6_flask/
git pull origin main

# Back up
cp data/inverted_index/la_index.db data/inverted_index/la_index.db.bak.$(date +%Y%m%d)

# Option A: Best quality (uses LatinPipe syntax database for lemmatization)
python scripts/build_inverted_index.py -l la --use-syntax-db --force

# Option B: Standard quality (CLTK + expanded UD table)
python scripts/build_inverted_index.py -l la --force
```

**Estimated time:** 2-4 hours for 1,429 Latin texts
**Expected output:** ~1,429 texts, ~800K+ lines, ~15M+ postings

**Note on `--use-syntax-db`:** This flag tells the build script to look up each line in the LatinPipe syntax database first. If LatinPipe has already parsed that line (which it has for most of the corpus), the build uses LatinPipe's lemmas instead of CLTK's. LatinPipe won the EvaLatin 2024 competition with ~90-95% accuracy, so this produces significantly better lemmatization.

**Note on `--force`:** Currently NOT implemented in the build script. Needs to be added before rebuild. The script currently only supports resume mode. See "Code Changes Needed" below.

### Step 2: Greek Index Rebuild

**On Marvin:**
```bash
# Back up
cp data/inverted_index/grc_index.db data/inverted_index/grc_index.db.bak.$(date +%Y%m%d)

# Rebuild (no syntax database for Greek yet)
python scripts/build_inverted_index.py -l grc --force
```

**Estimated time:** 1-2 hours for 659 Greek texts
**Expected output:** ~659 texts, ~400K+ lines

**Greek lemmatization quality:** CLTK's Greek lemmatizer + the 58K-entry UD table should provide good coverage. Greek has more complex morphology than Latin but the UD treebanks are well-curated.

### Step 3: English Index Rebuild

**On Marvin (or Replit — only 14 texts):**
```bash
# Back up
cp data/inverted_index/en_index.db data/inverted_index/en_index.db.bak.$(date +%Y%m%d)

# Rebuild
python scripts/build_inverted_index.py -l en --force
```

**Estimated time:** < 5 minutes for 14 English texts
**Note:** English can be rebuilt on Replit if preferred — the corpus is tiny.

### Step 4: Copy Rebuilt Indexes Back to Replit

```bash
# From Marvin, SCP to local machine, then upload to Replit:
scp marvin:/var/www/tesseraev6_flask/data/inverted_index/la_index.db .
scp marvin:/var/www/tesseraev6_flask/data/inverted_index/grc_index.db .
# Upload via Replit Files panel (drag into data/inverted_index/)
```

### Step 5: Verify with Reference Tests

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

---

## Code Changes Needed Before Rebuild

### 1. Add `--force` Flag to Build Script

The build script (`scripts/build_inverted_index.py`) currently only supports resume mode — it skips files already in the index. A `--force` flag needs to be added that:
- Drops and recreates all tables (texts, lines, postings)
- Processes every file from scratch
- Uses the improved lemma table for all texts

### 2. Verify `--use-syntax-db` Flag Works End-to-End

The syntax database integration was recently added. Before running the full rebuild:
- Test with 2-3 individual texts to confirm lemma quality
- Verify the syntax database lookup doesn't crash on edge cases
- Confirm postings, lines, and texts tables are all populated correctly

### 3. Consider Greek Lemma Table Expansion

The Greek lemma table (58K entries) was built from fewer UD treebanks. Before rebuilding Greek:
- Check which Greek UD treebanks are available (Perseus, PROIEL, plus any newer ones)
- Consider downloading additional treebanks to expand coverage (same process used for Latin)

---

## After the Rebuild: Cleanup

Once the rebuilt indexes are verified and working:

1. **The query-time fallback system can be kept as a safety net** — it adds negligible overhead and catches any remaining gaps
2. **Remove the `--use-syntax-db` workaround if Latin quality is good enough** without it
3. **Update `replit.md`** to note that indexes are rebuilt and the workaround is no longer primary
4. **Re-run the evaluation benchmark** (`evaluation/run_full_default_evaluation.py`) to measure impact on precision/recall

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| Feb 9, 2026 | Expand Latin lemma table to 62K entries | CLTK alone missed ~37% of forms in Neil Bernstein test case |
| Feb 9, 2026 | Build query-time reverse lookup as interim fix | Full index rebuild requires Marvin; this gives immediate improvement |
| Feb 9, 2026 | Fix distance filter to use min pairwise distance | Old span-based calculation falsely rejected prose matches with repeated words |
| Feb 9, 2026 | Plan full index rebuild on Marvin | Query-time workaround is effective but a proper rebuild is the permanent solution |
