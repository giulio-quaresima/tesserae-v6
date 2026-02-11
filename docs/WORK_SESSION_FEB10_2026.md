# Tesserae V6 Work Session — February 10, 2026

## Session Summary

Focus: Data distribution system and GitHub repository cleanup.

---

## Completed

### Data Packaging on Marvin
- Compressed 4 index files into `/var/www/tesseraev6_flask/public_data/`:
  - `inverted_index_latin.db.gz` (~900 MB)
  - `inverted_index_greek.db.gz` (~500 MB)
  - `inverted_index_english.db.gz` (~30 MB)
  - `syntax_latin.db.gz` (~250 MB)
- Updated `DATA_MANIFEST.json` with real SHA256 checksums and accurate file sizes
- Fixed `scripts/package_data.sh` argument handling bug
- Updated `scripts/download_data.py` to handle new manifest field names

### GitHub Repository Cleanup
- Removed 6 private files from Git tracking:
  - `docs/WORK_SESSION_FEB8_2026.md`
  - `docs/WORK_SESSION_FEB9_2026.md`
  - `docs/Tesserae_V6_Development_Workflow_Model.md`
  - `docs/ARTICLE_METHODS_DRAFT.md`
  - `deployment/tesserae.service`
  - `scripts/marvin_latinpipe/MARVIN_SETUP_GUIDE.md`
- Purged all 6 files from entire Git history using `git filter-repo`
- Consolidated branches: deleted `master`, `main` is now the sole branch
- Force-pushed cleaned history to GitHub

### Notes
- GitHub warns about `backend/embeddings/la/eobanus.iliad.npy` (59 MB) exceeding recommended 50 MB limit. Consider moving embeddings to data distribution system in the future.

---

## Pending — For Next Session

### 1. Apache Config for Data Downloads
- **Status:** Request sent (Feb 10) to configure Apache on Marvin
- **What's needed:** Serve `/var/www/tesseraev6_flask/public_data/` at `https://marvin.caset.buffalo.edu/tesserae-data/`
- **Once done:** Test download URLs and update `DATA_MANIFEST.json` with the final base URL

### 2. Copy `latin_lemmas_extended.db` to Marvin
- **Status:** File exists on Replit (15 MB) at `data/lemma_tables/latin_lemmas_extended.db`
- **What's needed:** Copy to Marvin, then re-run `scripts/package_data.sh` to include it in the data package
- **Method:** `scp` from a local machine, or download from Replit and upload to Marvin

### 3. Replit Git Sync — RESOLVED
- Resolved by removing `.git/index.lock` and running `git reset --hard origin/main` in the Shell
- Replit is now fully in sync with GitHub
