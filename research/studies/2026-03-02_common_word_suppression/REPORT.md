# Common-Word Suppression Study — March 1-2, 2026

## Objective

Eliminate common Latin function words (nec, tum, inde, quam, num, per, etc.)
from the top fusion results without regressing recall or creating a seesaw
between common-word bigrams and rare-word unigrams.

## Problem Statement

After Config K (three-layer rarity scoring, Feb 28), common-word pairs like
"nec absistit", "tum attono", "num campus", "inde aether" persisted in the
top 50 of Aen. 7 × Punica 2. Root causes:

1. **Geometric mean escape path** — A pair like "nec + absisto" (IDFs 0.444
   and 2.65) has geometric mean IDF ~1.08, landing in Zone 2 with only 42%
   penalty. The common word is carried by its rare partner.

2. **Lemmatization gap** — The inverted index stores inflected forms
   separately: "quem" (df=164) looks rare while its headword "qui" (df=1426)
   is extremely common.

3. **Seesaw dynamics** — Suppressing common-word bigrams exposed rare-word
   unigrams; suppressing unigrams re-elevated common bigrams. The penalty
   calibration had to be coordinated across all categories.

## Changes Made

### Phase 1: Min-IDF Gate + Headword Normalization (commit `8f38ec7`, Feb 28)

- **Min-IDF gate:** If ANY word in a matched pair has corpus IDF < 0.5,
  multiplier reduced by `RARITY_MIN_IDF_PENALTY`. Applied before Layer 1
  squaring.
- **Headword IDF normalization:** `_get_corpus_doc_freqs()` uses
  `max(lemma_df, headword_df)` via `latin_lemmas.json`. Fixes "quem"→"qui",
  "quos"→"qui", etc.

### Phase 2: Single-Word Penalty Rebalancing (commits `2d9d520`, `5d215e7`)

- `SINGLE_WORD_PENALTY` tuned: 0.5 → 0.25 → 0.15
- Convergence zeroing for `n_unique_words <= 1`
- No-significant-words penalty introduced (`NO_SIGNIFICANT_WORDS_PENALTY`)

### Phase 3: Continuous Zipf-like Convergence (commit `2d84129`, Mar 2)

The breakthrough: switched convergence IDF weight from geometric mean to
**minimum word IDF**:

```
idf_weight = min(1.0, min_word_idf) ** 2
```

This provides continuous Zipf-like scaling where the weakest word in a pair
gates the convergence contribution. "nec absistit" is gated by nec's
IDF=0.444, not rescued by absisto's IDF=2.65.

**Final parameter values:**

| Parameter | Before (Config K) | After |
|---|---|---|
| `RARITY_IDF_FLOOR` | 0.2 | 0.05 |
| `RARITY_MIN_IDF_PENALTY` | 1.0 (disabled) | 0.10 |
| `SINGLE_WORD_PENALTY` | 0.5 | 0.10 |
| `NO_SIGNIFICANT_WORDS_PENALTY` | 1.0 (N/A) | 0.12 |
| Convergence IDF weight | `min(1.0, geom_mean_idf)^2` | `min(1.0, min_word_idf)^2` |
| Convergence zeroing | single-word only | single-word OR no-sig-words |

## Results

### Ranking Quality: Aen. 7 × Punica 2

| Common-word pair | Before | After |
|---|---|---|
| num+campus | rank 23 | rank 169 |
| nec+absisto | rank 18 | rank 115 |
| tum+attono | rank 22 | >200 |
| inde+aether | rank 27 | rank 975 |
| mars+saeuus | rank 13 | rank 26 |
| ter+centum | rank 16 | rank 24 |

Top 15 results are all quality multi-word parallels (scores 2.9–14.0).
Zero function words in top 50.

### Recall: Unchanged

| Benchmark | Recall | Phase 2 |
|---|---|---|
| Lucan-Vergil | 195/213 (91.5%) | 192/213 (90.1%) |
| VF-Vergil | 466/521 (89.4%) | 472/521 (90.6%) |
| Achilleid-Vergil | 50/53 (94.3%) | 48/53 (90.6%) |
| Achilleid-Ovid | 21/23 (91.3%) | 23/23 (100.0%) |
| Achilleid-Thebaid | 50/52 (96.2%) | 48/52 (92.3%) |
| **Total** | **782/862 (90.7%)** | **783/862 (90.8%)** |

## Comparative Studies

### Fusion vs V3 Lemma Search (Mar 2)

Compared top 227 V3 lemma results with fusion rankings for Aen. 7 × Punica 2.

- **15 of 227** lemma results (6.6%) land in fusion's top 15 — these are
  the genuine quality parallels (serpens+hydra, aurum+trilix, etc.)
- **186 of 227** (81.9%) land at fusion rank 5000+ (median: rank 93,873) —
  these are ALL common-word bigrams (ipse+fero, per+urbs, ille+uolo,
  enim+neque, etc.) that V3 incorrectly ranks as top results due to lack
  of frequency awareness.
- Conclusion: The results absent from fusion's top ranks are common-word
  noise, not quality parallels.

### Fusion vs Rare Pairs Search (Mar 2)

Compared 254 rare bigrams (rarity ≥ 0.9) with fusion rankings for the
same text pair.

- **15 of 254** rare bigrams (5.9%) have at least one line pair in fusion's
  top 15 — all words genuinely distinctive (hydra+serpens, aurum+trilix,
  caeruleus+uadum, etc.)
- **212 of 254** (83.5%) are buried at rank 5000+ — these contain function
  words (nec, per, hic, atque, qui, iam, fero, sui) paired with content
  words. The bigram is "rare" in the corpus but the pair carries weak
  allusion signal.
- Rare pairs should NOT be added as a fusion channel: the 15 quality
  bigrams are already captured by existing channels + convergence bonus;
  adding rare_pair would double-count and inflate common-word scores.

## Key Technical Insights

1. **Geometric mean is fooled by asymmetric pairs.** A rare+common pair
   produces a moderate geometric mean that escapes binary thresholds. Using
   the minimum word IDF for convergence weighting provides continuous
   suppression proportional to the most common word.

2. **Seesaw dynamics require coordinated penalties.** The effective penalty
   for each category (common bigrams, no-sig bigrams, unigrams, sub-lexical)
   must be calibrated so that the ordering is always:
   quality bigrams > weak bigrams > unigrams > sub-lexical.

3. **V3 lemma search has no frequency awareness.** 82% of its top results
   are common-word noise. Fusion correctly identifies and demotes these.

4. **Rare pairs search conflates bigram rarity with allusion quality.**
   A function word paired with any content word produces a "rare" bigram,
   but the allusion signal is weak.

## Files

- Scoring engine: `backend/fusion.py`
- Vectorized optimizer: `evaluation/scripts/run_weight_optimization.py`
- Diagnostic: `evaluation/scripts/diagnose_top_results.py`
- Fusion vs lemma comparison: `evaluation/scripts/compare_fusion_vs_lemma.py`
- Fusion vs rare pairs comparison: `evaluation/scripts/compare_fusion_vs_rarepairs.py`
- Benchmark: `evaluation/scripts/benchmark_production_fusion.py`
