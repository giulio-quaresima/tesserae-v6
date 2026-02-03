# V6 No Stoplist Evaluation

**Date:** February 3, 2026  
**Test Configuration:** No stoplist (stoplist_size=-1)  
**Benchmark:** Lucan BC1 vs Vergil Aeneid (bench41.txt)

---

## Settings Tested

| Parameter | Value | Notes |
|-----------|-------|-------|
| match_type | lemma | |
| min_matches | 2 | |
| max_distance | 20 | |
| **stoplist_size** | **-1** | No stoplist at all |
| unit_type | line | |
| max_results | 500 | |

---

## Results Summary

| Metric | Result |
|--------|--------|
| **Precision@10** | TBD |
| **Type 4-5 Recall** | 37.1% (79/213) |
| **Lexical Recall** | 75.0% (39/52) |
| Total Results | 6,000 |

---

## Comparison with Default (curated stoplist)

| Metric | Default | No Stoplist | Change |
|--------|---------|-------------|--------|
| Type 4-5 Recall | 26.8% | **37.1%** | **+38%** |
| Lexical Recall | 61.5% | **75.0%** | **+22%** |
| Total Results | 1,170 | 6,000 | +413% |

---

## Interpretation

Removing the stoplist significantly improves recall:

1. **13.5% more lexical parallels found** — From 32 to 39 out of 52
2. **22 more Type 4-5 parallels found** — From 57 to 79 out of 213
3. **Trade-off: More results to review** — 6,000 vs 1,170

The curated stoplist includes words that form valid scholarly parallels in this benchmark.

---

## Stoplist Size Comparison

| Configuration | Lexical | Type 4-5 | Results |
|---------------|---------|----------|---------|
| Default (curated+Zipf) | 61.5% | 26.8% | 1,170 |
| **No stoplist** | **75.0%** | **37.1%** | 6,000 |
| Top 5 words | 69.2% | 32.4% | 3,370 |
| Top 10 words | 65.4% | 28.2% | 1,986 |

---

## Recommendation

For scholarly research requiring maximum recall, consider:
1. Using no stoplist (stoplist_size=-1)
2. Or minimal stoplist (stoplist_size=5)

The default curated stoplist prioritizes precision over recall.
