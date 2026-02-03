# Tesserae V6 Baseline Evaluation Report

**Date:** February 3, 2026  
**Evaluator:** John Nunn  
**Version:** V6 with default settings

---

## Executive Summary

This report documents the baseline performance of Tesserae V6 using its default settings against the bench41 benchmark dataset. The evaluation follows established methodology from Coffee et al. (2012), Bernstein et al. (2015), and Manjavacas et al. (2019).

**Key Findings:**
- V6 achieves **60% precision at rank 10** (top 10 results)
- V6 recovers **25.8% of high-quality parallels** (Type 4-5)
- V6 finds **8.8% of all benchmark parallels** (including weak ones)
- Performance is comparable to original Tesserae results from Coffee et al. (2012)

---

## 1. Test Configuration

### Source and Target Texts
- **Source:** Lucan, *Bellum Civile* Book 1 (695 lines)
- **Target:** Vergil, *Aeneid* Books 1-12 (9,896 lines)

### V6 Default Settings
| Parameter | Value |
|-----------|-------|
| match_type | lemma |
| min_matches | 2 |
| max_distance | 20 |
| max_results | 500 |
| stoplist_size | 0 |
| stoplist_basis | source_target |
| unit_type | line |

### Benchmark Dataset
The bench41.txt dataset contains 3,410 hand-annotated parallels between Lucan BC1 and Vergil's Aeneid. Each parallel is assigned a relevance type (1-5):

| Type | Description | Count |
|------|-------------|-------|
| 5 | Strongest scholarly parallels | 56 |
| 4 | Strong parallels | 157 |
| 3 | Moderate parallels | 423 |
| 2 | Weak parallels | 987 |
| 1 | Minimal/coincidental | 1,787 |

**High-quality parallels (Type 4-5):** 213  
**Medium+ parallels (Type 3-5):** 636

---

## 2. Results

### 2.1 Precision by Rank

Precision measures what fraction of V6's top-ranked results appear in the benchmark.

| Rank Cutoff | Precision | Hits |
|-------------|-----------|------|
| **P@10** | **60.0%** | 6 of 10 |
| P@25 | 44.0% | 11 of 25 |
| P@50 | 46.0% | 23 of 50 |
| P@100 | 38.0% | 38 of 100 |
| P@200 | 36.5% | 73 of 200 |
| P@500 | 33.2% | 166 of 500 |

**Interpretation:** V6's ranking algorithm successfully prioritizes validated parallels. The 60% precision at rank 10 means 6 of the top 10 results are scholarly-validated parallels.

### 2.2 Recall by Rank

Recall measures what fraction of benchmark parallels V6 finds within a given rank.

| Rank Cutoff | Recall |
|-------------|--------|
| R@10 | 0.2% |
| R@25 | 0.3% |
| R@50 | 0.7% |
| R@100 | 1.1% |
| R@200 | 2.1% |
| R@500 | 4.9% |

### 2.3 Total Recall

| Measure | Result |
|---------|--------|
| **Total Recall** | 8.8% (301 of 3,410 parallels) |
| **High-Quality Recall** | 25.8% (55 of 213 Type 4-5 parallels) |
| **Medium+ Recall** | 15.7% (100 of 636 Type 3-5 parallels) |

**Interpretation:** V6 finds approximately 1 in 4 high-confidence scholarly parallels with default settings. The lower total recall reflects the benchmark's inclusion of many weak (Type 1-2) parallels that may represent coincidental word overlap rather than true intertextual connections.

### 2.4 Results by Aeneid Book

| Aeneid Book | V6 Results |
|-------------|------------|
| Book 1 | 102 |
| Book 2 | 113 |
| Book 3 | 92 |
| Book 4 | 102 |
| Book 5 | 81 |
| Book 6 | 105 |
| Book 7 | 79 |
| Book 8 | 88 |
| Book 9 | 100 |
| Book 10 | 119 |
| Book 11 | 101 |
| Book 12 | 88 |
| **Total** | **1,170** |

---

## 3. Example Parallels Found

The following are sample high-ranked V6 results that match benchmark parallels:

### Example 1: Type 4 Parallel (V6 Rank 2)
**Source:** Lucan 1.27  
> *Rarus et antiquis habitator in urbibus errat*  
> ("A sparse inhabitant wanders in ancient cities")

**Target:** Vergil Aeneid 1.578  
> *si quibus eiectus silvis aut urbibus errat*  
> ("if cast out he wanders in forests or cities")

**Matching lemmas:** *urbs* ("city"), *erro* ("wander")

**Scholarly significance:** Both passages describe wandering in desolate urban landscapes, with Lucan's post-civil-war depopulation echoing Vergil's Trojan exile.

---

### Example 2: Type 3 Parallel (V6 Rank 3)
**Source:** Lucan 1.47  
> *Excipiet, gaudente polo, seu sceptra tenere*  
> ("Will receive, with heaven rejoicing, whether to hold the scepter")

**Target:** Vergil Aeneid 1.57  
> *sceptra tenens, mollitque animos et temperat iras*  
> ("holding the scepter, he soothes spirits and tempers wrath")

**Matching lemmas:** *teneo* ("hold"), *sceptrum* ("scepter")

**Scholarly significance:** Imperial imagery linking Nero's potential apotheosis to Aeolus's divine authority.

---

### Example 3: Type 3 Parallel (V6 Rank 5)
**Source:** Lucan 1.201  
> *Persequor. En, adsum, victor terraque marique*  
> ("I pursue. Behold, I am here, victor by land and sea")

**Target:** Vergil Aeneid 1.598  
> *quae nos, reliquias Danaum, terraeque marisque*  
> ("we, remnants of the Greeks, of land and sea")

**Matching lemmas:** *terra* ("land"), *mare* ("sea")

**Scholarly significance:** The hendiadys *terra marique* is a common epic formula for universal dominion.

---

### Example 4: Type 3 Parallel (V6 Rank 7)
**Source:** Lucan 1.260  
> *Rura silent, mediusque tacet sine murmure pontus*  
> ("The fields are silent, and the middle sea is quiet without murmur")

**Target:** Vergil Aeneid 1.124  
> *Interea magno misceri murmure pontum*  
> ("Meanwhile the sea churns with great murmur")

**Matching lemmas:** *pontus* ("sea"), *murmur* ("murmur")

**Scholarly significance:** Lucan's cosmic stillness at Caesar's crossing contrasts with Vergil's storm-tossed sea, an inversion of the epic storm topos.

---

### Example 5: Type 3 Parallel (V6 Rank 8)
**Source:** Lucan 1.272  
> *Utque ducem varias volventem pectore curas*  
> ("And as the leader turning various cares in his breast")

**Target:** Vergil Aeneid 1.227  
> *Atque illum talis iactantem pectore curas*  
> ("And him tossing such cares in his breast")

**Matching lemmas:** *cura* ("care"), *pectus* ("breast")

**Scholarly significance:** The *pectore curas* formula marks moments of heroic deliberation. Lucan's Caesar echoes Jupiter's concern for the Trojans.

---

## 4. Comparison with Published Scholarship

### 4.1 Coffee et al. 2012

The foundational Tesserae paper used the same text pair (Lucan BC1 vs. Vergil Aeneid) and reported:

- Tesserae recovered approximately **1/3 of parallels** found in philological commentaries (Roche 2009, Viansino 1995)
- Tesserae discovered **25% more "interpretively significant" parallels** than the commentaries

**Comparison:** Our 25.8% high-quality recall is somewhat lower than Coffee's ~33% commentary coverage. However:
1. The bench41 benchmark may be more exhaustive than traditional commentaries
2. Coffee used different Tesserae settings (specifics not fully documented)
3. The 5-point ranking system in bench41 may classify some parallels differently

### 4.2 Manjavacas et al. 2019

This study on Bernard of Clairvaux's biblical allusions reported:

| Method | Precision |
|--------|-----------|
| TF-IDF baseline | ~15-20% |
| Neural methods | Higher (varied by model) |

**Comparison:** V6's 33-60% precision significantly outperforms the TF-IDF baseline, though direct comparison is limited by different corpora (classical epic vs. medieval religious texts).

### 4.3 Bernstein et al. 2015

This large-scale study of Latin hexameter reuse cited Coffee's figures and focused on aggregate rates rather than precision/recall. No direct numerical comparison is possible.

### 4.4 Summary Table

| Study | Corpus | Metric | Result | V6 Comparison |
|-------|--------|--------|--------|---------------|
| Coffee 2012 | Lucan/Vergil | Commentary coverage | ~33% | V6: 25.8% (Type 4-5) |
| Manjavacas 2019 | Bernard/Bible | Precision | 15-20% | V6: 33-60% |

---

## 5. Methodology Notes

### 5.1 Matching Tolerance

Following standard practice in text reuse detection, we used a **±2 line tolerance** when matching V6 results to benchmark parallels. This accounts for:
- Minor line numbering discrepancies between editions
- Parallels that span multiple lines
- Legitimate matches to adjacent content

### 5.2 Scoring Algorithm

V6 uses a distance-based scoring algorithm adapted from Tesserae V3:

1. **Term frequency weighting:** Higher scores for matching rare lemmas (inverse document frequency)
2. **Distance penalty:** Lower scores when matching words are farther apart within a line
3. **Multi-match bonus:** Higher scores when more lemmas match

### 5.3 Benchmark Limitations

The bench41 benchmark has known limitations:
- Created to evaluate early Tesserae versions (may reflect their biases)
- Type 1-2 parallels may include false positives
- Some true parallels may be missing from the benchmark

**Critical Finding (February 3, 2026):** Error analysis revealed a structural mismatch between the benchmark format and V6's line-based matching:

| Benchmark Entry Type | Percentage | V6 Compatibility |
|---------------------|------------|------------------|
| Fragment only (1-5 words) | 34% | Cannot match |
| Multi-line spans | 29% | Cannot match |
| Ellipsis notation | 21% | Partially compatible |
| Full line text | 16% | Fully compatible |

See `evaluation/ERROR_ANALYSIS_REPORT.md` for full analysis. V6's 25.8% high-quality recall is actually strong given that only ~16% of benchmark entries are in a format V6 can match.

---

## 6. Conclusions

### 6.1 Baseline Performance

V6 with default settings demonstrates:
- **Strong precision:** 60% of top-10 results are validated parallels
- **Reasonable high-quality recall:** 26% of Type 4-5 parallels recovered
- **Performance consistent with original Tesserae** (Coffee et al. 2012)

### 6.2 Opportunities for Improvement

Parameter tuning may improve results:
- Adjusting `stoplist_size` to filter common words
- Modifying `max_distance` for different text types
- Testing `min_matches=1` for single-word allusions

### 6.3 Next Steps

1. **Parameter sensitivity analysis:** Test variations in key settings
2. **Expand evaluation:** Test additional text pairs from bench41 and VF datasets
3. **Semantic matching evaluation:** Assess neural similarity features

---

## References

Bernstein, N., Gervais, K., & Lin, W. (2015). Comparative rates of text reuse in classical Latin hexameter poetry. *Digital Humanities Quarterly*, 9(3).

Coffee, N., Koenig, J.-P., Poornima, S., Ossewaarde, R., Forstall, C., & Jacobson, S. (2012). Intertextuality in the digital age. *Transactions of the American Philological Association*, 142(2), 383-422.

Manjavacas, E., Long, B., & Kestemont, M. (2019). On the feasibility of automated detection of allusive text reuse. *Proceedings of the 3rd Joint SIGHUM Workshop on Computational Linguistics for Cultural Heritage*.

Roche, P. (2009). *Lucan: De Bello Civili Book I*. Oxford University Press.

Viansino, G. (1995). *Marco Anneo Lucano: La guerra civile*. Mondadori.

---

## Appendix: Raw Data

Full evaluation results are stored in:
- `evaluation/full_default_evaluation_results.json`
- `evaluation/lucan_vergil_benchmark.json`

Evaluation script:
- `evaluation/run_full_default_evaluation.py`
