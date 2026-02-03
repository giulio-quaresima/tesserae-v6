# V6 Phrase Matching Evaluation

**Date:** February 3, 2026  
**Test Configuration:** Phrase-based matching  
**Benchmark:** Lucan BC1 vs Vergil Aeneid (bench41.txt)

---

## Settings Tested

| Parameter | Value |
|-----------|-------|
| match_type | lemma |
| min_matches | 2 |
| max_distance | 20 |
| stoplist_size | 0 |
| unit_type | **phrase** |
| max_results | 500 |

---

## Results Summary

| Metric | Result |
|--------|--------|
| **Precision@10** | 10.0% |
| **Type 4-5 Recall** | 25.4% (54/213) |
| **Lexical Recall** | 61.5% (32/52) |
| Total Results | 1,009 |

---

## Comparison with Line Matching (Default)

| Metric | Line | Phrase | Change |
|--------|------|--------|--------|
| Precision@10 | 60.0% | 10.0% | -50% |
| Type 4-5 Recall | 25.8% | 25.4% | -0.4% |
| Lexical Recall | 61.5% | 61.5% | 0% |
| Total Results | 1,170 | 1,009 | -161 |

---

## Interpretation

Phrase matching **does not improve recall** and **significantly hurts precision**.

Possible explanations:
1. Phrase segmentation in V6 may not align with benchmark spans
2. Phrases may be too short to capture multi-line parallels
3. The matching words may still fall in different phrase units

---

## Conclusion

**Phrase matching is not beneficial for this benchmark.** Line-based matching remains the better default.

---

## Next Steps

Consider testing:
- Stoplist variations (stoplist_size=10, 20)
- Distance variations (max_distance=50, 100)
- min_matches=1 (if benchmark has single-word entries)
