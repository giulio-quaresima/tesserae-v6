# V6 Default Settings Evaluation

**Date:** February 3, 2026  
**Test Configuration:** Line-based matching with V6 defaults  
**Benchmark:** Lucan BC1 vs Vergil Aeneid (bench41.txt)

---

## Settings Tested

| Parameter | Value |
|-----------|-------|
| match_type | lemma |
| min_matches | 2 |
| max_distance | 20 |
| stoplist_size | 0 |
| unit_type | **line** |
| max_results | 500 |

---

## Results Summary

| Metric | Result |
|--------|--------|
| **Precision@10** | 60.0% |
| Precision@100 | 38.0% |
| Precision@500 | 33.2% |
| **Type 4-5 Recall** | 25.8% (55/213) |
| **Lexical Recall** | 61.5% (32/52) |
| Total Results | 1,170 |

---

## Benchmark Analysis

### Composition of Type 4-5 Parallels (213 total)

| Category | Count | % | V6 Compatible? |
|----------|-------|---|----------------|
| Thematic (no word overlap) | 161 | 76% | No |
| Lexical (2+ word overlap) | 52 | 24% | Partially |
| — Same-line lexical | ~32 | 15% | Yes |
| — Multi-line lexical | ~20 | 9% | No |

### Key Finding

V6 finds **61.5% of lexical parallels** (those with actual word overlap). The remaining 38.5% of lexical parallels require multi-line span matching — the matching words appear on different lines in source and/or target.

---

## Sample Found Parallels

| Rank | Source | Target | Matching Lemmas | Type |
|------|--------|--------|-----------------|------|
| 2 | BC1.27 | Aen.1.578 | urbs, erro | 4 |
| 3 | BC1.47 | Aen.1.57 | teneo, sceptrum | 3 |
| 5 | BC1.201 | Aen.1.598 | terra, mare | 3 |
| 7 | BC1.260 | Aen.1.124 | pontus, murmur | 3 |
| 8 | BC1.272 | Aen.1.227 | cura, pectus | 3 |

---

## Missed Parallel Analysis

Example of missed lexical parallel (BC1.1 → Aen.7.41):
- Benchmark lists overlap: ['bella', 'acies']
- Actual locations:
  - 'bella': BC1.1, Aen.7.41
  - 'acies': BC1.4, Aen.7.42
- Words span different lines — V6 cannot match

---

## Interpretation

1. **Precision is strong** — V6 ranks valid parallels highly
2. **Lexical recall is solid** — 61.5% when limited to word-based parallels
3. **Lower overall recall explained** — benchmark includes thematic/conceptual parallels

---

## Comparison with Published Work

| Source | Metric | Value |
|--------|--------|-------|
| Coffee et al. 2012 | Commentary coverage | ~33% |
| Manjavacas et al. 2019 | TF-IDF precision | 15-20% |
| **V6 (this test)** | Precision@10 | 60% |
| **V6 (this test)** | Lexical recall | 61.5% |

---

## Next Test: Phrase Matching

Test phrase-based unit matching to see if multi-line spans improve recall.
