# V6 Default Settings Evaluation (Baseline)

**Date:** February 3, 2026  
**Test Configuration:** Default settings with curated stoplist  
**Benchmark:** Lucan BC1 vs Vergil Aeneid (bench41.txt)

---

## Settings Tested

| Parameter | Value | Notes |
|-----------|-------|-------|
| match_type | lemma | |
| min_matches | 2 | |
| max_distance | 20 | |
| **stoplist_size** | **0 (Default)** | Curated list + Zipf detection (~70 words) |
| unit_type | line | |
| max_results | 500 | |

---

## Results Summary

| Metric | Result |
|--------|--------|
| **Precision@10** | 60.0% |
| **Type 4-5 Recall** | 26.8% (57/213) |
| **Lexical Recall** | 61.5% (32/52) |
| Total Results | 1,170 |

---

## Key Finding

The default curated stoplist filters out words that contribute to benchmark parallels. See V6_NO_STOPLIST_EVALUATION.md for improved results.

---

## Benchmark Characteristics

| Category | Count | Notes |
|----------|-------|-------|
| Total BC1 parallels | 3,410 | Full bench41.txt |
| Type 4-5 parallels | 213 | High-quality scholarly annotations |
| Lexical parallels | 52 | Have ≥2 shared words |
| Thematic only | 161 | No word overlap (V6 cannot detect) |

---

## Interpretation

1. **Precision is strong** — V6 ranks valid parallels highly (60% P@10)
2. **Lexical recall is solid** — 61.5% when limited to word-based parallels
3. **Lower overall recall explained** — benchmark includes thematic/conceptual parallels that V6 cannot detect by design
