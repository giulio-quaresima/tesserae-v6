# Next Steps for Benchmark Evaluation

**Created:** February 5, 2026  
**Status:** Queued for future work

---

## 1. Search for Additional V3/V5 Resources

Check if there are other semantic matching or scoring resources from earlier Tesserae versions that could be useful:
- Additional synonym dictionaries
- Feature weights or scoring configurations
- Benchmark test results from V3/V5

---

## 2. Test Synonym Expansion Beyond Top 2

The V3 design deliberately limits synonyms to top 2 per headword. Test whether allowing more synonyms improves recall without degrading precision:
- Try top 3, top 5, top 10 synonyms
- Measure recall change on benchmark parallels
- Measure precision impact (noise increase)
- Determine optimal cutoff

---

## 3. Explore Scoring Thresholds vs Hard Cutoffs

Current approach uses min_matches=2 as a hard cutoff. Investigate alternative approaches:
- Continuous scoring that doesn't eliminate sub-threshold matches
- Semantic boost for 1-lemma matches to recover sub-threshold parallels
- Combined scoring: lemma count + IDF + semantic similarity as weighted sum

---

## Related Files

- Benchmark report: `reports/BENCHMARK_EVALUATION_REPORT.md`
- V3 synonyms: `data/synonymy/fixed_latin_syn_lem.csv`
- V3 derivation docs: `data/synonymy/V3_SYNONYM_DERIVATION.md`
- IDF validation: `data/analysis/idf_scoring_validation.json`
