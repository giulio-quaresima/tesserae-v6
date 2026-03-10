# Tesserae V6 — Collaborator Setup Guide

This guide is for collaborators who have SSH access to Marvin. It walks you through getting a working copy of Tesserae V6 on your own machine.

---

## Prerequisites

- Python 3.10 or later
- SSH access to the Tesserae server (`tesserae.caset.buffalo.edu`)
- Git

---

## Step 1: Clone the Code

```bash
git clone https://github.com/tesserae/tesserae-v6.git
cd tesserae-v6
```

---

## Step 2: Copy Data Files from Marvin

The repository includes text files, embeddings, and lemma tables, but the search index databases (~5.3 GB total) are too large for GitHub. Since you have Marvin access, copy them directly:

```bash
# Required — search indexes
scp tesserae.caset.buffalo.edu:/var/www/tesseraev6_flask/data/inverted_index/la_index.db data/inverted_index/
scp tesserae.caset.buffalo.edu:/var/www/tesseraev6_flask/data/inverted_index/grc_index.db data/inverted_index/
scp tesserae.caset.buffalo.edu:/var/www/tesseraev6_flask/data/inverted_index/en_index.db data/inverted_index/

# Optional — Latin syntax parses (1.6 GB, needed for syntax-based scoring)
scp tesserae.caset.buffalo.edu:/var/www/tesseraev6_flask/data/inverted_index/syntax_latin.db data/inverted_index/

# Optional — extended Latin lemma table (15 MB)
scp tesserae.caset.buffalo.edu:/var/www/tesseraev6_flask/data/lemma_tables/latin_lemmas_extended.db data/lemma_tables/
```

If you are already on Marvin, you can use `cp` instead of `scp`:

```bash
cp /var/www/tesseraev6_flask/data/inverted_index/la_index.db data/inverted_index/
cp /var/www/tesseraev6_flask/data/inverted_index/grc_index.db data/inverted_index/
cp /var/www/tesseraev6_flask/data/inverted_index/en_index.db data/inverted_index/
cp /var/www/tesseraev6_flask/data/inverted_index/syntax_latin.db data/inverted_index/
cp /var/www/tesseraev6_flask/data/lemma_tables/latin_lemmas_extended.db data/lemma_tables/
```

---

## Step 3: Install Python Dependencies

```bash
pip install -r requirements.txt
```

On first run, some NLP libraries may download additional model files automatically.

---

## Step 4: Run the Application

```bash
python main.py
```

The app will start on `http://localhost:5000`. Open that in your browser.

---

## Verifying Your Setup

To confirm the data files are in place before running:

```bash
python scripts/download_data.py --check
```

This reports which files are present and which are missing.

---

## Alternative: Public Download

Data files are also available for public download at `https://tesserae.caset.buffalo.edu/tesserae-data/`. You can fetch them automatically:

```bash
python scripts/download_data.py
```

This will download and extract all required data files automatically. The `DATA_MANIFEST.json` file in the project root lists all downloadable files with checksums.

---

## What's What

| Directory | In Git? | Contents |
|-----------|---------|----------|
| `texts/` | Yes | 2,176 `.tess` text files (~308 MB) |
| `backend/embeddings/` | Yes | Pre-computed semantic embeddings (~2 GB) |
| `data/lemma_tables/*.json` | Yes | Lemma lookup tables (~40 MB) |
| `data/pedecerto/` | Yes | Metrical scansion XML data |
| `cache/` | Yes | Pre-computed frequencies and rare words |
| `data/inverted_index/*.db` | No | Search indexes (~5.3 GB) — copied in Step 2 |

For full details, see `docs/DATA_FILES_REFERENCE.md`.
