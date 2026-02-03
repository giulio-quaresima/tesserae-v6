# V6 Stoplist=5 Evaluation

**Date:** February 3, 2026  
**Test Configuration:** Line matching with stoplist_size=5  
**Benchmark:** Lucan BC1 vs Vergil Aeneid (bench41.txt)

---

## Settings Tested

| Parameter | Value |
|-----------|-------|
| match_type | lemma |
| min_matches | 2 |
| max_distance | 20 |
| **stoplist_size** | **5** |
| unit_type | line |
| max_results | 500 |

---

## Results Summary

| Metric | Result |
|--------|--------|
| **Precision@10** | 10.0% |
| **Type 4-5 Recall** | 32.4% (69/213) |
| **Lexical Recall** | 69.2% (36/52) |
| Total Results | 3,370 |

---

## Comparison with Default (stoplist=0)

| Metric | Default | Stoplist=5 | Change |
|--------|---------|------------|--------|
| Type 4-5 Recall | 26.8% | **32.4%** | **+21%** |
| Lexical Recall | 61.5% | **69.2%** | **+13%** |
| Total Results | 1,170 | 3,370 | +188% |

---

## Interpretation

A small stoplist (5 most common words) **significantly improves recall**:

1. **More results returned** — 3,370 vs 1,170
2. **More benchmark parallels found** — Removing very common words allows content words to match
3. **Precision@10 unchanged** — Still 10% (1 of top 10 in benchmark)

The improvement suggests that common words were "crowding out" meaningful matches in the scoring.

---

## Stoplist Size Sweep Results

| Size | Lexical | Type 4-5 | Results |
|------|---------|----------|---------|
| 0 | 61.5% | 26.8% | 1,170 |
| **5** | **69.2%** | **32.4%** | 3,370 |
| 10 | 65.4% | 28.2% | 1,986 |
| 15 | 61.5% | 26.8% | 1,698 |
| 20 | 57.7% | 23.5% | 1,313 |

Stoplist=5 is optimal. Larger stoplists hurt recall by filtering meaningful words.

---

## Recommendation

**Consider changing V6 default from stoplist_size=0 to stoplist_size=5** for improved recall on scholarly benchmarks.
