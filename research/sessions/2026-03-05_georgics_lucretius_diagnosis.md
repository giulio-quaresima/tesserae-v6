# Georgics-Lucretius Plague Parallel: System Diagnosis (2026-03-05)

## Context

Thomas (1986, 179-180) discusses how Vergil's plague narrative in Georgics 3 recalls the Athenian plague in Lucretius DRN 6. He highlights:
- Rare adverbs *minutatim* and *cateruatim* shared between the two texts
- Georg. 3.481 / DRN 6.1140 as pure syntactic imitation: "not a single word is shared" yet "the reminiscence is incontrovertible"

We ran Vergil Georgics vs Lucretius DRN 6 in fusion search and investigated why the system struggled with these specific parallels.

## Findings

### 1. cateruatim (Georg. 3.556 / DRN 6.1144) — Rank ~14,282

Three compounding problems:

- **rare_word threshold:** doc_freq=52, just above the `rare_word_max_occurrences=50` threshold. Misses by 2.
- **"do" filtered:** The only other shared lemma is *do* (from *dat*/*dabantur*), but "do" has length 2 and is filtered by the `len(feature) > 2` check in `matcher.py` line 433. So only *cateruatim* counts as a shared lemma — below min_matches=2.
- **Single-word penalty:** Only `lemma_min1` and `exact` fire. Single-word penalty 0.12, squared to 0.0144, crushes the score.

### 2. minutatim (Georg. 3.484-485 / DRN 6.1190-1191) — Rank 1080

- **rare_word threshold:** doc_freq=55, also above the 50 threshold.
- **Window saves it partially:** The window match pairs *minutatim* with *traho* (2 shared lemmas), enabling the full lemma channel. But *traho* (df=849, IDF=0.52) pulls the geometric mean IDF down, and convergence is nearly zeroed because min_word_idf=0.52.
- Score 0.34, rank 1080. Better than cateruatim but still low for a word appearing in only ~55 texts.

### 3. Georg. 3.481 / DRN 6.1140 (Thomas's tricolon) — NOT FOUND

**Source:** "corrupitque lacus, infecit pabula tabo"
**Target:** "vastavitque vias, exhausit civibus urbem"
Zero shared words or lemmas.

Three channels came close:

#### Dictionary channel: no synonym pairs
None of the semantically related word pairs (corrupo/vasto, inficio/exhaurio) exist in the V3 synonym database. `conrumpo` is not in the DB at all. `exhaurio` synonyms are only {depleo, emulgeo, exintero}.

#### Semantic channel: above threshold but filtered by cap
SPhilBERTa cosine similarity = **0.5787** (above the 0.5 threshold). But DRN 6.1140 ranks **280th** among all DRN 6 lines for similarity to Georg. 3.481. The `semantic_top_n=100` cap filters it out. There are 741 DRN 6 lines above 0.5 similarity — plague/destruction vocabulary saturates the channel.

#### Syntax channel: identical structure but pruning prevents evaluation
Both lines have **identical dependency head structures**: `[0, 1, 4, 1, 4, 4, 1]`. The tricolon pattern Thomas describes is perfectly captured. But syntax channel uses lemma-inverted-index pruning (only evaluates pairs sharing >=1 lemma). Zero shared lemmas = never evaluated.

Additionally, LatinPipe mislabels "vastavitque" as CCONJ (should be VERB with enclitic -que) and fails to lemmatize it.

## Potential Fixes

| Issue | Fix | Risk |
|-------|-----|------|
| rare_word threshold | Raise from 50 to 60-100 | More results, slightly lower precision |
| Single-word rare penalty | Consider IDF-scaled penalty (rarer = less penalty) | Complex |
| Dictionary gaps | Add corrupo/vasto, inficio/exhaurio to synonym DB | Manual curation needed |
| Semantic top_n cap | Raise from 100 to 200-300, or make text-pair-adaptive | Performance cost |
| Syntax lemma pruning | Remove shared-lemma requirement for syntax | Major performance cost — evaluates all O(n*m) pairs |

## Syntax Channel: Detailed Research on Relaxing Lemma Gate

### Current architecture
- **Pruning gate** (line 642-655 of fusion.py): Only generates candidate pairs sharing >=1 lemma
- **Scoring function** (`_compute_syntax_score`, line 513-589): Scores based on deprel/upos agreement at shared lemma positions. Returns 0.0 if no shared lemmas.
- **Structure signature bonus** (lines 567-587): Compares core argument overlap (Jaccard on deprel labels), independent of lemmas. But only additive — requires passing the lemma gate first.

### Cost of removing lemma gate
- Georgics × DRN 6: 2,509,479 all-pairs vs 271,271 lemma-gated (9.3x increase)
- Lucan BC 1 × Aeneid: ~1,367,180 all-pairs vs 109,651 gated (~12.5x increase)
- Current syntax takes ~20s for 109K pairs with 8 workers → ungated would be ~250s (4+ min), adding significant time to each search

### The fundamental problem
The scoring function itself is lemma-dependent: it measures deprel/upos agreement for *shared* lemma positions. For Georg 3.481/DRN 6.1140 (zero shared lemmas), it would return 0.0 even without the gate. A new scoring function is needed.

### Proposed approach: Pure structural similarity
For ungated pairs, use a different scoring function that compares:
1. **Head pattern similarity:** Compare dependency head arrays directly (e.g., `[0,1,4,1,4,4,1]` vs `[0,1,4,1,4,4,1]`). Use normalized edit distance or exact match.
2. **Deprel sequence similarity:** Compare sorted core deprel labels (Jaccard). This is the existing structure signature bonus, extracted as standalone.
3. **Argument structure fingerprint:** Hash of (nsubj count, obj count, obl count, etc.) — fast pre-filter.

The approach would be two-tier:
- **Tier 1 (fast filter):** Compare argument structure fingerprints. Only pairs with identical or near-identical fingerprints proceed.
- **Tier 2 (detailed scoring):** Compare full head patterns and deprel sequences.

This keeps the O(n*m) comparisons manageable because Tier 1 is just integer comparison.

### Alternative: Semantic-gated syntax
Instead of removing the lemma gate entirely, add semantic similarity as an alternative gate: if two lines have SPhilBERTa cosine > 0.5 but no shared lemmas, also check syntax. This leverages existing precomputed data (the semantic similarity matrix) to identify candidate pairs for syntax comparison. Much cheaper than all-pairs.

### Risk assessment
- Pure structural approach may produce many false positives (common syntactic patterns in Latin verse)
- Semantic-gated approach is more targeted but couples two channels
- Either approach needs benchmark validation

## Fixes Applied

### Fix 1: Raise rare_word_max_occurrences from 50 to 100
- **minutatim:** Rank 1080 → **241** (4.5x). Now detected by lemma + rare_word + dictionary (3 channels)
- **cateruatim:** Rank ~14,282 → **4,171** (3.4x). Now detected by lemma_min1 + rare_word (2 channels)
- Benchmark: 800/862 (92.8%), zero regression

### Fix 2: Structural fingerprint matching (syntax channel Path B)
- New `_compute_structural_score()` compares head/deprel/upos patterns for pairs with no shared lemmas
- Fingerprint index: only exact head-pattern matches of length >= 3
- Georg 3.481/DRN 6.1140: **now found at rank 402** (structural score 0.84)
- Negligible performance overhead (+0.3–0.6% candidates per search)

### Fix 3: Two-tier semantic recovery
- After all channels run, look up cosine similarity for structural pairs filtered by semantic top-100 cap
- Georg 3.481/DRN 6.1140 has cosine 0.579 → recovered and injected as semantic result
- Fusion combines syntax_structural (1.5 × 0.84) + semantic (1.2 × 0.579) + convergence
- **Georg 3.481/DRN 6.1140: rank 245** (final)

### Remaining unresolved
- Dictionary gaps (corrupo/vasto, inficio/exhaurio) — would require manual synonym DB curation
- LatinPipe mislabeling "vastavitque" as CCONJ — upstream parser issue

## For the DHQ Article

These findings are written up as a case study in the DHQ article draft, section "Case Studies" > "The Limits of Lexical Detection: Vergil's Plague and Lucretius." The case study presents the diagnosis nearly verbatim and anticipates incorporation of solutions.
