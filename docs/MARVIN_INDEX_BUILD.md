# Complete Inverted Index Build on Marvin

## Background

The Latin inverted index (`data/inverted_index/la_index.db`) was originally built on January 25, 2026 on Replit. The build was interrupted by an out-of-memory crash partway through the alphabetical file list, stopping around the letter "O" (mid-Ovid). This left **509 of 1,429** Latin texts unindexed — the entire P–W range plus scattered gaps in A–O.

The Greek index (`grc_index.db`) is similarly partial: 514 of 659 texts (77%).

The build script supports **resume mode**, so it will only process the missing files.

## Step-by-Step Instructions

### 1. SSH into Marvin

```bash
ssh marvin
cd /var/www/tesseraev6_flask/
```

### 2. Pull latest code (includes the fixed build script)

```bash
git pull origin main
```

The key fix: `build_inverted_index.py` and `index_single_text()` now populate **both** the `postings` table (for lemma lookups) and the `lines` table (for displaying text content in results). The original build only populated `postings`.

### 3. Back up the current indexes

```bash
cp data/inverted_index/la_index.db data/inverted_index/la_index.db.bak
cp data/inverted_index/grc_index.db data/inverted_index/grc_index.db.bak
```

### 4. Run the index builder (resume mode is automatic)

```bash
# Latin only (the main priority):
python scripts/build_inverted_index.py -l la

# Or all languages:
python scripts/build_inverted_index.py -l all
```

**Expected behavior:**
- It will report "Resuming: 920 files already indexed" for Latin
- It will process the remaining ~509 Latin files
- Each file takes a few seconds (total ~30-60 minutes depending on Marvin's speed)
- Progress is printed every 50 files
- The database is committed every 50 files, so it's safe to interrupt

**Expected output when complete:**
- Latin: ~1,429 texts indexed, ~2GB index file
- Greek: ~659 texts indexed (if running `all`)

### 5. Verify the build

```bash
python3 -c "
import sqlite3
for lang in ['la', 'grc', 'en']:
    db = f'data/inverted_index/{lang}_index.db'
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM texts')
        texts = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM lines')
        lines = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM postings')
        postings = cur.fetchone()[0]
        conn.close()
        print(f'{lang}: {texts} texts, {lines} lines, {postings} postings')
    except Exception as e:
        print(f'{lang}: {e}')
"
```

**Expected:**
- la: ~1429 texts, ~800K+ lines, ~15M+ postings
- grc: ~659 texts (if rebuilt)
- en: 14 texts (already complete)

### 6. Copy the completed index back to Replit

Option A — SCP from Marvin to your local machine, then upload to Replit:
```bash
# On your local machine:
scp marvin:/var/www/tesseraev6_flask/data/inverted_index/la_index.db .
scp marvin:/var/www/tesseraev6_flask/data/inverted_index/grc_index.db .
# Then upload to Replit via the Files panel (drag and drop into data/inverted_index/)
```

Option B — If Replit SSH is available:
```bash
# From Marvin:
scp data/inverted_index/la_index.db replit:/home/runner/workspace/data/inverted_index/
```

Option C — Use rsync for large files (recommended):
```bash
rsync -avz --progress data/inverted_index/la_index.db youruser@replit-host:workspace/data/inverted_index/
```

### 7. Verify on Replit after uploading

Run the reference tests from `tests/search_reference_tests.md`:

```bash
# Lemma search test
curl -s -X POST "http://localhost:5000/api/line-search" \
  -H "Content-Type: application/json" \
  -d '{"query": "arma virum", "language": "la", "search_type": "lemma", "stoplist_size": 10, "max_results": 500}'

# Exact string search test  
curl -s -X POST "http://localhost:5000/api/line-search" \
  -H "Content-Type: application/json" \
  -d '{"query": "arma virum", "language": "la", "search_type": "exact", "max_results": 500}'
```

**Expected with full index:**
- Lemma search: ~400+ results (up from 302 with partial index)
- Exact search: ~50+ results (up from 38)
- All previously missing authors (Plautus, Silius Italicus, Seneca complete works, etc.) should appear

### 8. Also backfill lines data for the original 900 texts

The original 900 texts were built before the `lines` table fix. Check if they already have lines data:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/inverted_index/la_index.db')
cur = conn.cursor()
cur.execute('''
    SELECT COUNT(DISTINCT t.text_id) 
    FROM texts t 
    LEFT JOIN lines l ON t.text_id = l.text_id 
    WHERE l.text_id IS NULL
''')
missing_lines = cur.fetchone()[0]
print(f'Texts missing lines data: {missing_lines}')
conn.close()
"
```

If any texts are missing lines data, they were indexed before the fix. The resume build won't re-process them (they're already in the `texts` table). To backfill, you can run:

```bash
python3 -c "
import sqlite3, json, os, sys
sys.path.insert(0, '.')
from backend.text_processor import TextProcessor
tp = TextProcessor()

db = 'data/inverted_index/la_index.db'
conn = sqlite3.connect(db)
cur = conn.cursor()

cur.execute('''
    SELECT t.text_id, t.filename 
    FROM texts t 
    LEFT JOIN lines l ON t.text_id = l.text_id 
    WHERE l.text_id IS NULL
''')
missing = cur.fetchall()
print(f'Backfilling lines for {len(missing)} texts...')

for i, (text_id, filename) in enumerate(missing):
    filepath = os.path.join('texts/la', filename)
    if not os.path.exists(filepath):
        continue
    units = tp.process_file(filepath, 'la', unit_type='line')
    for unit in units:
        cur.execute('INSERT OR IGNORE INTO lines (text_id, ref, content, lemmas, tokens) VALUES (?, ?, ?, ?, ?)',
            (text_id, unit.get('ref',''), unit.get('text',''), 
             json.dumps(unit.get('lemmas',[])), json.dumps(unit.get('tokens',[]))))
    if (i+1) % 50 == 0:
        conn.commit()
        print(f'  {i+1}/{len(missing)}...')

conn.commit()
conn.close()
print('Done!')
"
```

## What Was Missing and Why

| Letter Range | Status | Count |
|-------------|--------|-------|
| A–O | Mostly indexed, scattered gaps | ~115 missing |
| P–W | Completely unindexed | ~394 missing |
| **Total** | | **509 missing** |

Key missing authors: Seneca (26), Prudentius (23), Petrus Riga (23), Tertullian (22), Plautus (20), Silius Italicus (18), Statius (15 additional), Quintilian (13), Pliny (18), Vergil pseudo-works (11).

**Root cause:** The original build on Jan 25 ran out of memory on Replit after processing ~900 files alphabetically. It was never restarted to completion.
