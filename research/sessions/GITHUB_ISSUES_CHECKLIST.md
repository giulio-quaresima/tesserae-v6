# Tesserae V6 — GitHub Issues Checklist

Private working copy of open issues from https://github.com/tesserae/tesserae-v6/issues
Generated 2026-02-24. Close issues on GitHub after pushing to production.

## Status Key
- [ ] Not started
- [~] Fixed on dev, not yet pushed to production
- [x] Pushed to production and closed on GitHub

---

## Issues

### #3 — Enable HTTPS on Marvin production server
- [ ] **Status:** ON VOLUNTEER LIST
- **Labels:** CS Student, Tesserae Fellow
- **Details:** Marvin serves over HTTP, causing security issues, browser compatibility problems (DuckDuckGo blocks HTTP API requests), and "Not Secure" warnings. Steps: obtain SSL certificate, install on Marvin, configure Apache VirtualHost for port 443, add HTTP→HTTPS redirect, verify no hardcoded `http://` URLs in frontend.

### #4 — Rare Pairs: Add sort by order of occurrence
- [~] **Status:** DONE. Fixed on dev.
- **Labels:** CS Student
- **Details:** Add option to sort rare word pairs by order of occurrence in the text (for line-by-line commentary work), in addition to current rarity sorting. Submitted by Neil Bernstein.

### #5 — Rare Pairs: Add stoplist options
- [~] **Status:** DONE. Fixed on dev.
- **Labels:** CS Student
- **Details:** Add stoplist options to exclude common words from rare pairs results as with the main phrase search. Submitted by Neil Bernstein.

### #6 — Rare Words: Add proper noun filter option
- [~] **Status:** DONE. Fixed on dev.
- **Labels:** CS Student, Tesserae Fellow
- **Details:** Rare words results are mostly proper nouns. Add option to filter out or de-prioritize proper nouns. Submitted by Neil Bernstein (Ohio University).
- **Notes:** Implemented ratio-based PN detection (50% threshold, 20-location sample), local-context OR for homographs (e.g., Achates), conservative enclitic stripping (-que only), prefix notation cleanup. 119 PNs excluded in Aen×BC test. "Exclude proper nouns" checkbox in UI.

### #7 — Timeline graphs should update with prose/poetry filter
- [~] **Status:** DONE. Fixed on dev
- **Labels:** CS Student
- **Details:** In corpus search results, selecting/deselecting prose or poetry doesn't update timeline column graphs. They erroneously show all results regardless of filter.
- **Notes:** Fixed across CorpusSearchResults, LineSearch, WildcardSearch. Now shows "No results match the current genre filter" instead of blank chart.

### #8 — Add dictionary links for rare words
- [~] **Status:** DONE. Fixed on dev
- **Labels:** CS Student
- **Details:** Add clickable links to external dictionary definitions in Rare Words Explorer. Latin: Logeion. Greek: Logeion. English: Wiktionary.
- **Notes:** Already implemented — Logeion links for Latin/Greek, Wiktionary for English.

### #9 — Audit and improve mobile responsiveness
- [ ] **Status:** ON VOLUNTEER LIST
- **Labels:** CS Student
- **Details:** Audit all major views on small screens. Ensure touch-friendly UI, verify corpus browser, results display, and repository work on mobile.

### #10 — Properly classify all works as prose or poetry
- [ ] **Status:** DONE. REMOVE FROM VOLUNTEER LIST
- **Labels:** Tesserae Fellow
- **Details:** Lactantius and other authors have works erroneously classified as poetry. Use admin tools to survey and reclassify.

### #11 — Text Eras
- [ ] **Status:** DONE. REMOVE FROM VOLUNTEER LIST
- **Labels:** Faculty Developer
- **Details:** Establish source of date identifications. Make Date Authority File. Add Era field in user text ingestion page. Add text metadata modification tool to admin.

### #12 — Make sure all downloads from Downloads page work
- [ ] **Status:** DONE
- **Labels:** CS Student, Tesserae Fellow
- **Details:** Downloads for benchmark sets are not working. Check all downloads.

### #13 — Blank graphs with string search with no results in prose/poetry
- [~] **Status:** DONE. Fixed on dev
- **Labels:** CS Student
- **Details:** String search for Latin "divum" returns only poetic results. Clicking Timelines with only prose checkbox shows blank chart frame rather than "no results" message.
- **Notes:** Same fix as #7 — empty genre filter now shows message instead of blank chart across all search views.

### #14 — Add diacritics for Greek rare word explorer
- [~] **Status:** DONE. Fixed on dev
- **Details:** Greek rare words now show proper polytonic diacritics (breathings + accents). 56% coverage from corpus data; remaining are orphan frequency entries (same as production).

### #15 — Developer Data Files Download Error: Extended Latin Lemma Table
- [ ] **Status:** DONE. Fixed on dev. 
- **Details:** Clicking "Extended Latin Lemma Table" download causes 404 error.

### #16 — Title Rendering in Results
- [~] **Status:** DONE. Fixed on dev
- **Details:** Titles rendered incorrectly when tags shared with other titles (e.g., "Seneca, Heroides o" instead of "Seneca, Hercules Oetaeus"). Fixed.

### #17 — Lemma returning only exact matches
- [~] **Status:** DONE. Fixed on dev.
- **Details:** Lemma match type sometimes only matches identical forms. Sil. 6.186 should match Stat. Theb. 6.93 but doesn't.
- **Notes:** Fixed Feb 25. Three-layer problem: (1) LatinPipe syntax DB produced wrong lemmata for *effero* forms (`extulit`→`extuio`, `extulerat`→`exfero`); (2) CLTK appended sense-disambiguation digits (`effero1`) that broke matching; (3) stale lemma caches preserved bad data. Fix: stripped trailing digits in `text_processor.py`, added 43 missing *effero* paradigm forms to `latin_lemmas.json`, corrected 209 lines in `syntax_latin.db` and `la_index.db`, cleaned 294K cached lemma entries across 1,393 Latin files.

### #18 — "Phrase" vs "line" as the unit type
- [ ] **Status:** Not started
- **Details:** Phrase vs line finds slightly different counts but nothing actually found outside a single line. Test case: Stat. Theb. 6.93 vs Sil. 6.185-6.

### #19 — Extending line matching?
- [ ] **Status:** Not started
- **Details:** Implement generic "within X lines/words" option, as in previous versions' multi-line search. Reported by Dr. Krasne.

### #20 — Email notifications for site admin list
- [ ] **Status:** Not started
- **Details:** Addresses in admin Notification Email Addresses list do not receive notifications for feedback or text submissions.

### #21 — Text addition upload not working
- [ ] **Status:** Not started
- **Details:** Admins not alerted and texts not received when submitted through Help and Support > Upload Your Text > Submit Your Formatted Text.

### #22 — Add credits for text edition to the corpus viewer
- [ ] **Status:** Not started
- **Details:** Update corpus viewer to indicate "Added by" credits, as in the list from Tesserae's former blog.

### #23 — Assign text addition credits
- [ ] **Status:** Not started
- **Details:** Assign "Added by" credits on Corpus Viewer page. From V3 Blog corpus list, Carolingian additions, Dr. Coffee, V6 additions.

### #24 — Main Search Required Fields
- [ ] **Status:** Not started
- **Details:** Make "author" and "work" required fields in main search.

---

## Non-GitHub Issues (Dev Notes)

### Optimize hapax-search endpoint performance
- [ ] **Status:** Not started
- **Details:** `/api/hapax-search` (rare word search between two texts) is slow for large text pairs (Aen × Lucan BC: ~290s). Bottleneck is `lookup_lemma_locations()` called once per shared rare lemma — hundreds of individual SQL queries + file I/O. Should batch location lookups (same pattern as dictionary channel inverted-index optimization).

---

## Summary

| Status | Count |
|--------|-------|
| Not started | 13 |
| Fixed on dev | 9 |
| Pushed to production | 0 |
| **Total** | **22** |

*Last updated: 2026-02-25*
