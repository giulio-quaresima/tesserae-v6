# Recall Improvement Plan: Miss Analysis + Sentence-Level Search

## Context

Config D_weighted finds 163/213 (76.5%) on Lucan-Vergil and 440/521 (84.5%) on VF-Vergil — all at **line level**. The remaining ~50 LV and ~81 VF misses need characterization, and fixing the broken phrase/sentence mode is a high-priority improvement path.

**Key finding:** `unit_type='phrase'` exists end-to-end in the codebase but is **inverted** — `split_into_phrases()` in `text_processor.py` splits individual lines into *smaller* sub-line fragments at `.;?!` marks, instead of *combining* consecutive lines into multi-line sentence units. This was documented in a Replit agent session (Feb 4, commits `1d62ac9`, `3e68bdd`, `9fe3ca8`). All evaluations to date use `unit_type='line'`.

---

## 1. Precision & F-Scores (Reference)

Traditional precision is meaningless (0.1% — system returns ~154K pairs). P@K is the right metric:

### Config D_weighted (best ranking)

| Benchmark | P@10 | P@50 | P@100 | Recall | F1@100 |
|-----------|------|------|-------|--------|--------|
| Lucan-Vergil | 50% | 30% | 23% | 76.53% | 14.70% |
| VF-Vergil | 90% | 46% | 44% | 84.45% | 14.17% |

---

## 2. Estimated Miss Taxonomy

| Category | Est. share | Addressable by |
|----------|-----------|----------------|
| A. Thematic, no shared vocabulary | ~40% | Fine-tuned embeddings (Phase 3) |
| B. Allusion by inversion | ~15% | Anti-parallel scoring (Phase 2) |
| **C. Multi-line / enjambed** | **~15%** | **Sentence-level search (Phase 1)** |
| D. Lemmatization failures | ~10% | Lemma audit (Phase 1) |
| E. Structural/narrative | ~10% | Passage-level comparison (Phase 3) |
| F. Mediated via third text | ~10% | Cross-text triangulation (Phase 3) |

---

## 3. Implementation Plan

### Phase 0: Miss Analysis (do first, ~15 min)

**Goal:** See the actual 50 LV / 81 VF misses with their text and features.

**Files to modify:**
- `evaluation/scripts/analyze_missed_pairs.py` — update to use 9-channel configs, definitive benchmark paths (`evaluation/benchmarks/`), unbounded+tuned semantic settings

**Output:**
- `evaluation/results/definitive_evaluation/missed_pairs_analysis.json` — per-miss: loci, type (4/5), both lines' text, shared lemmas, shared tokens, sound sim, semantic score, fuzzy pairs, tractability flags
- `evaluation/results/definitive_evaluation/MISSED_PAIRS_ANALYSIS.md` — human-readable summary with category counts

**Run in tmux** (~5 min execution).

---

### Phase 1: Fix Sentence-Level Search (main effort)

**The bug:** `text_processor.py:split_into_phrases()` (lines 231-242) calls `re.split(r'[.;?!]', text)` on each `.tess` line independently. This produces sub-line fragments. It should instead accumulate consecutive lines into sentence units, splitting only when sentence-ending punctuation is encountered.

**1a. Fix `process_file()` to support `unit_type='sentence'`**

File: `backend/text_processor.py`

New behavior for `unit_type='sentence'`:
- Read `.tess` lines sequentially
- Accumulate tokens/text into a buffer
- When a sentence-ending punctuation mark is encountered (`.`, `?`, `!` — NOT `;` or `:` for Latin), emit the accumulated buffer as one unit
- The unit's ref should indicate the line range: e.g., `vergil.aeneid.1.1-1.3`
- Handle edge cases: lines with no sentence-ending punctuation (continuation), lines with multiple sentences (split and emit each), last line of file (emit whatever is buffered)

**Punctuation decisions:**
- Sentence-enders: `.` `?` `!` (and Greek `·` high dot)
- NOT sentence-enders: `;` (Latin semicolon = clause boundary, not sentence end in most editorial practice), `:` (already excluded)
- This differs from the current `split_into_phrases()` which treats `;` as a delimiter — for true sentence mode, `;` should NOT split

**1b. Wire sentence mode through the matcher**

File: `backend/matcher.py`

- No changes needed to matching logic itself — it already operates on whatever units `text_processor` provides
- Verify that unit refs with ranges (e.g., `1.1-1.3`) don't break any downstream code (scoring, result formatting, benchmark evaluation)

**1c. Add `unit_type='sentence'` option to evaluation scripts**

File: `evaluation/scripts/run_evaluation.py` (lines 266-267)

- Add a parameter to run evaluations with `unit_type='sentence'`
- The benchmark gold files use single-line refs (e.g., `luc. 1.1`). For sentence-mode evaluation, a match should count if the gold ref falls within the sentence unit's line range.

**1d. Run comparative evaluation**

- Run the 9-channel fusion with `unit_type='sentence'` on all 5 benchmarks
- Compare recall and P@K against line-level results
- Specifically check whether the ~15% of misses in Category C (enjambed parallels) are now found

**1e. Supplementary: line + sentence fusion**

- Run both line-level and sentence-level searches, union the results
- This may catch both single-line and multi-line parallels without sacrificing either

---

### Phase 1 (continued): Quick wins

**1f. Lemmatization audit**
- Run the 50 missed pairs through `text_processor` and check for lemma failures
- Fix specific gaps in lookup tables
- File: `backend/text_processor.py`, `data/lemma_tables/`

**1g. Scorer semantic gate check**
- Verify that `scorer.py`'s `min_content_matches` + `semantic_score < 0.92` gate isn't re-filtering what the tuned semantic matcher (`0match_high`, threshold=0.85) already found
- File: `backend/scorer.py`

---

### Phase 2: Medium-effort (after Phase 1 results)

- **Anti-parallel detection** — boost when lemma overlap is high but semantic similarity is low
- **Formulaic pattern channel** — shared lemma bigrams/trigrams
- **Proper name equivalences** — small lookup table

### Phase 3: Research-level (longer term)

- Passage-level embeddings
- Fine-tuned allusion model
- Cross-text triangulation

---

## 4. Critical Files

| File | Role |
|------|------|
| `backend/text_processor.py` | Fix `split_into_phrases()`, add sentence accumulation logic |
| `backend/matcher.py` | Verify sentence-length units work |
| `backend/scorer.py` | Check semantic gate thresholds |
| `evaluation/scripts/analyze_missed_pairs.py` | Update for 9-channel miss analysis |
| `evaluation/scripts/run_evaluation.py` | Add sentence unit_type support |
| `evaluation/benchmarks/*.json` | Gold files (read-only, but evaluation needs range-matching) |

---

## 5. Verification

1. **Phase 0:** Run miss analysis → review the 50 misses → categorize manually
2. **Phase 1 (sentence):**
   - Unit test: process a known enjambed passage and verify sentence units span the right lines
   - Regression: "arma virum" search must still return Ovid, Quintilian, Seneca
   - Evaluation: 9-channel fusion at sentence level on all 5 benchmarks
   - Compare: line-only vs sentence-only vs line+sentence union
3. **Track P@K** alongside recall — sentence mode should not degrade ranking quality
