# Tesserae V6 Data Files Reference

## Quick Summary

Most data files are included in the Git repository. The only files you need to download separately are the **SQLite search indexes** (~5.3 GB total). A script handles this automatically.

```bash
git clone https://github.com/tesserae/tesserae-v6.git
cd tesserae-v6
pip install -r requirements.txt
python scripts/download_data.py    # Downloads ~5.3 GB of index files
python main.py                     # Ready to go
```

To check what's present or missing without downloading:
```bash
python scripts/download_data.py --check
```

---

## What's in Git vs. What Needs Downloading

### Included in the Git Repository

| Directory | Size | Contents |
|-----------|------|----------|
| `texts/` | ~308 MB | 2,176 `.tess` text files (Latin, Greek, English) |
| `backend/embeddings/` | ~2 GB | Pre-computed semantic embeddings (SPhilBERTa, MiniLM) |
| `data/lemma_tables/*.json` | ~40 MB | Lemma lookup tables (Latin, Greek) |
| `data/pedecerto/` | ~5 MB | Metrical scansion XML data |
| `cache/` | ~5 MB | Pre-computed rare words and bigrams |

### NOT in Git — Download Separately

These are SQLite database files (blocked by `*.db` in `.gitignore`). They are hosted at `https://marvin.caset.buffalo.edu/tesserae-data/`.

| File | Size | Required? | Description |
|------|------|-----------|-------------|
| `data/inverted_index/la_index.db` | 2.2 GB | Yes | Latin search index (1,429 texts, 298,757 lemmas) |
| `data/inverted_index/grc_index.db` | 1.4 GB | Yes | Greek search index (659 texts, 360,429 lemmas) |
| `data/inverted_index/en_index.db` | 79 MB | Yes | English search index (14 texts, 22,867 lemmas) |
| `data/inverted_index/syntax_latin.db` | 1.6 GB | No | Latin syntax parses (LatinPipe UD annotations) |
| `data/lemma_tables/latin_lemmas_extended.db` | 15 MB | No | Extended Latin lemma table |

**Total to download: ~5.3 GB**

The manifest of all downloadable files, including URLs, sizes, and checksums, is maintained in `DATA_MANIFEST.json` at the project root.

---

## How the Download System Works

### For Collaborators (after cloning from GitHub)

```bash
python scripts/download_data.py              # Download all files
python scripts/download_data.py --check      # Check status only
python scripts/download_data.py --file la    # Download Latin index only
python scripts/download_data.py --file grc   # Download Greek index only
python scripts/download_data.py --force      # Re-download everything
```

The script reads `DATA_MANIFEST.json`, downloads compressed archives from Marvin, extracts them to the correct directories, and verifies SHA256 checksums.

### For Maintainers (after rebuilding indexes on Marvin)

After rebuilding an index, re-package the data files for download:

```bash
bash scripts/package_data.sh
```

This compresses each `.db` file, generates checksums, updates `DATA_MANIFEST.json`, copies everything to the Apache public directory, and creates an HTML index page. Then commit the updated `DATA_MANIFEST.json` to Git so collaborators get the new checksums.

---

## Rebuilding Data Files

If you need to rebuild any of these files from scratch:

| Data | How to Rebuild | Time |
|------|---------------|------|
| **Latin index** | `python scripts/build_inverted_index.py --language la --use-syntax-db --force` | ~30 min |
| **Greek index** | `python scripts/build_inverted_index.py --language grc --fast --force` | ~10 min |
| **English index** | `python scripts/build_inverted_index.py --language en --force` | ~2 min |
| **Syntax DB** | `python scripts/marvin_latinpipe/build_latinpipe_syntax.py` (on Marvin) | ~1-2 hours |
| **Lemma tables** | `python scripts/build_lemmas.py` | ~5 min |
| **Embeddings** | Embedding generation scripts in `embedding_toolkit/` | ~30 min/language |
| **Cache** | Auto-rebuilds on first use | Automatic |

---

## Keeping Data Files Updated

Most of the time, nothing changes. The index files only need updating when you add new texts, rebuild an index with improved lemmatization, or re-parse the syntax database.

### When You Update an Index (Maintainer Workflow)

1. **Rebuild the index on Marvin** using the build scripts above
2. **Re-run the packaging script:**
   ```bash
   bash scripts/package_data.sh
   ```
   This re-compresses the updated `.db` files, generates new SHA256 checksums, updates `DATA_MANIFEST.json`, and replaces the old downloads on the Apache server.
3. **Commit the updated `DATA_MANIFEST.json` to Git:**
   ```bash
   git add DATA_MANIFEST.json
   git commit -m "Update data manifest with new index checksums"
   git push
   ```
   This ensures collaborators see the new checksums when they pull.

### When a Collaborator Needs the Latest Data

1. **Pull the latest code** (which includes the updated manifest):
   ```bash
   git pull
   ```
2. **Re-run the download script:**
   ```bash
   python scripts/download_data.py --force
   ```
   Without `--force`, the script skips files that already exist locally. Use `--force` to replace them with the latest versions, or delete the specific `.db` file and re-run without `--force`.

### What Triggers an Update?

| Event | What to Rebuild | How Often |
|-------|----------------|-----------|
| New texts added to corpus | Inverted index for that language | Occasionally |
| Lemmatization improvements | Inverted index (full rebuild) | Rarely |
| LatinPipe re-parse | `syntax_latin.db` | Rarely |
| New embedding model | Embeddings (already in Git) | Very rarely |

There is no automatic notification when indexes are updated. Inform collaborators when you push a new manifest ("Pull and re-run the download script").

---

## Notes

1. **`.gitignore` blocks `*.db` files** — This is why the SQLite indexes don't end up on GitHub even though their parent directories are tracked.
2. **The texts are on GitHub** — Unlike many large NLP projects, the full text corpus is committed to Git (~308 MB).
3. **Embeddings are on GitHub** — The ~2 GB of pre-computed embeddings are also committed. This was a deliberate choice for ease of setup.
4. **Index rebuilds require texts** — You need the text corpus present before rebuilding any search index.
5. **Syntax DB requires LatinPipe** — The syntax database can only be rebuilt on Marvin where the LatinPipe model is available.
