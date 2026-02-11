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

### 4. Implement Syntax Matching for Lemma Search (Latin)

The full Latin corpus has been parsed with LatinPipe and stored in `syntax_latin.db` (1,429 texts, 542,311 lines). The next step is to wire this data into the scoring pipeline.

#### Phase 1: Syntax Boost for Lemma Search (priority)

When a lemma search finds matching lines, apply a syntax-based score boost at the **whole-line level**:

1. After the lemma matcher identifies a result pair (source line + target line sharing lemmas), look up both lines in `syntax_latin.db` by text_id and line reference.
2. Compare the **full syntactic structure** of both lines — dependency relations, grammatical roles, word order — not just the syntax around the matched lemma tokens.
3. The rationale: if two lines share vocabulary *and* have similar grammatical structure overall, that is a much stronger signal of genuine allusion. For example, a line where "arma" is the subject and "virum" is the object should score higher against another line with the same structure than against one where those words fill different roles.
4. Apply this as a **score boost** (multiplier) to the existing V3 distance+IDF score. Syntax similarity should elevate strong matches, not filter out results that lack syntax data.
5. Latin only — Greek and English do not have full-corpus parses yet.

**Technical steps:**
- Replace the current `SyntaxMatcher.load_treebanks()` (which reads small CoNLL-U treebank files from `data/treebanks/`) with direct lookups into `syntax_latin.db` by (text_id, ref).
- The search pipeline already has text_id and line reference for each result — pass these through to the syntax scorer.
- Adjust `feature_extractor.py` so the syntax boost applies to the full line comparison, not just the matched-term pair.
- The UI toggle ("Syntax matching") already exists in search settings.

#### Phase 2: Standalone Syntax Search (deferred)

A separate search mode where users search by syntactic pattern — e.g., "find all lines with the same dependency structure as Aeneid 1.1." This is a different, more complex feature to be built later.

### 5. Work Session Files Lost in Git Purge

The Feb 8 and Feb 9 work session documents were unintentionally destroyed during the `git filter-repo` purge. The tool rewrites entire Git history to remove files from every commit; when Replit was then reset to match the rewritten remote, the local copies were also lost. The files should have been backed up outside the Git tree before the purge. Future private files should be added to `.gitignore` before committing, rather than purged after the fact.
