# Fusion Search Architecture

## Overview

Tesserae V6's fusion search combines nine independent matching channels into a single ranked result list using weighted score fusion. Each channel detects textual parallels through a different linguistic signal — from exact lexical overlap to phonetic similarity to distributional semantics — and the fusion layer combines these signals with empirically validated weights and a convergence bonus that rewards cross-channel agreement.

The search uses a **two-pass line/window architecture** that runs the full channel battery on individual verse lines, then selectively re-runs a subset of channels on sliding 2-line windows to capture allusions that span line breaks (enjambment). The channel selection for the window pass follows from a formal classification of channels by their matching granularity.

## Channel Taxonomy

The nine channels are classified into four types based on the **level of linguistic representation** at which they operate. This classification determines both their contribution to intertext detection and their behavior under textual unit variation (line vs. window).

### Lexical channels

Match on the **identity** of word forms or dictionary headwords within a textual unit.

| Channel | Signal | Criterion |
|---------|--------|-----------|
| **lemma** | Shared dictionary headwords | ≥ 2 shared lemmata after frequency-based stoplist filtering |
| **lemma_min1** | Single shared headword | ≥ 1 shared lemma (high-recall, low-precision variant) |
| **exact** | Identical surface tokens | ≥ 2 shared orthographic forms after stoplist filtering |
| **rare_word** | Shared low-frequency lemmata | ≥ 2 shared lemmata with corpus frequency ≤ 50 |

**Key property**: Lexical channels require the matching tokens to **co-occur within a single textual unit**. A match between units (s_i, t_j) means that both units contain the relevant lemmata or forms. When an allusion is split across a line break (enjambment), the matching tokens are distributed between s_i and s_{i+1}, and neither line alone meets the co-occurrence threshold. Combining them into a 2-line window recovers the match.

### Sub-lexical channels

Match on **character-level similarity** between individual token pairs.

| Channel | Signal | Criterion |
|---------|--------|-----------|
| **edit_distance** | Levenshtein distance | Token pairs with ≥ 60% normalized similarity, ≥ 1 shared character trigram |
| **sound** | Character trigram overlap | Jaccard similarity of trigram sets, ≥ 25% threshold |

**Key property**: Sub-lexical channels compare **individual tokens pairwise** across all source and target units. If token A in s_i is phonetically similar to token B in t_j, this relationship is detected in the line pass regardless of whether adjacent lines are considered. Expanding the unit to a 2-line window does not introduce new token pairs that were not already compared — it only re-evaluates the same tokens in a combined context, producing redundant matches.

### Distributional channels

Match on **semantic relatedness** between individual lemmata or tokens, using either learned vector representations or curated synonym resources.

| Channel | Signal | Criterion |
|---------|--------|-----------|
| **semantic** | Contextual embedding similarity | SPhilBERTa cosine similarity ≥ 0.5 for token pairs |
| **dictionary** | Curated synonym pairs | Shared entries in Latin/Greek synonym tables (Lewis & Short, V3 synonymy) |

**Key property**: Like sub-lexical channels, distributional channels enumerate **pairwise relationships between individual lemmata**. If lemma A in s_i is a synonym of lemma B in t_j, this is found in the line pass. Windowing does not create new lemma pairs; it only re-evaluates existing pairs in a combined context.

### Structural channels

Match on **syntactic patterns** derived from dependency parses.

| Channel | Signal | Criterion |
|---------|--------|-----------|
| **syntax** | Dependency-tree pattern overlap | Shared UD dependency triples (currently pre-computed) |

**Key property**: Syntax matches are computed from pre-parsed treebanks and are currently available only at the line level.

## Two-Pass Architecture

### Rationale

Classical verse is composed in lines, but allusions frequently span line breaks. In Latin hexameter poetry, enjambment is a deliberate stylistic choice, and the shared vocabulary of an allusion may be distributed across two consecutive lines. A search that operates only on individual lines will miss these cases.

The standard solution is to search over sliding windows of *n* consecutive lines in addition to individual lines. However, running all channels on windows is computationally expensive: window units contain twice the tokens of line units, and the three most expensive channels (edit_distance, dictionary, semantic) exhibit quadratic or near-quadratic scaling with token count.

### Design

The channel taxonomy provides a principled basis for selective windowing:

**Pass 1 — Line-level (all 9 channels)**: This is the primary search. All channels run on individual verse lines, providing complete coverage of every matching signal.

**Pass 2 — Window-level (lexical channels only)**: Only channels that require **token co-occurrence within a unit** benefit from expanded windows. These are the lexical channels: lemma, lemma_min1, exact, and rare_word.

Sub-lexical and distributional channels are excluded from the window pass because they measure **pairwise relationships between individual tokens** that are already exhaustively enumerated in the line pass. Expanding the unit size does not introduce new comparisons.

### Empirical validation

Profiling on Vergil's *Georgics* (2,183 lines) vs. Lucan's *Bellum Civile* (8,061 lines) confirmed this design:

| Metric | All channels on windows | Lexical channels only |
|--------|------------------------|----------------------|
| edit_distance window matches not found at line level | 0 | — |
| sound window matches not found at line level | 7 | — |
| Window pass time | 436s | ~72s (est.) |
| Window pass as % of total | 70% | ~28% |

The three excluded channels consumed 364 of the 436 seconds of window-pass time (84%) while producing effectively zero novel matches.

### Result merging

Line and window results are merged with deduplication: line results take priority, and a window result is included only if it covers at least one source×target line pair not already present in the line results. This ensures that enjambed allusions are captured without inflating the result count with redundant entries.

## Scoring

### Weighted score fusion

Each channel independently scores its matches using Tesserae's V3 scoring function (inverse document frequency weighted by token distance). The fusion layer combines these per-channel scores:

```
fused_score = Σ (channel_score_i × weight_i) + 0.5 × (N - 1)
```

where N is the number of channels that independently found the pair.

### Channel weights

Weights were determined by systematic ablation across five benchmark pairs (Feb 2026). Each weight reflects the channel's independent contribution to recall, with higher weights assigned to channels that uniquely identify true parallels:

| Channel | Weight | Type |
|---------|--------|------|
| edit_distance | 4.0 | sub-lexical |
| sound | 3.0 | sub-lexical |
| exact | 2.0 | lexical |
| lemma | 1.5 | lexical |
| dictionary | 1.0 | distributional |
| semantic | 0.8 | distributional |
| rare_word | 0.5 | lexical |
| syntax | 0.5 | structural |
| lemma_min1 | 0.3 | lexical |

### Convergence bonus

A bonus of +0.5 is added for each additional channel beyond the first that confirms a pair. This rewards **cross-channel convergence**: when multiple independent signals agree that a pair is a parallel, this is stronger evidence than a high score from any single channel. The bonus is linear in the number of confirming channels, reflecting the assumption that each additional confirmation is approximately equally informative.

### Per-channel candidate pruning

Each channel retains at most its top 50,000 scored results before fusion. This is standard rank-based candidate pruning in multi-source fusion pipelines. Results below a channel's top 50K have negligible marginal contribution to fused scores (channel_score × weight), especially for low-weight channels (e.g., lemma_min1 at weight 0.3). This cap reduces memory consumption and fusion time without affecting the top fused results.

## Performance Characteristics

Benchmarked on Vergil's *Georgics* (2,183 lines) × Lucan's *Bellum Civile* (8,061 lines), 32-core server:

| Configuration | Total time | Notes |
|---------------|-----------|-------|
| All channels, both passes (no optimization) | 619s | Baseline |
| Selective window channels + result caps | ~250s (est.) | 2.5× speedup |
| Line pass only (no windows) | 184s | Misses enjambed allusions |

The parallelization of CPU-intensive channels (edit_distance, sound) across 8 worker processes via `ProcessPoolExecutor` provides a further 3–5× speedup within those channels.

## Default Result Limit

The default `max_results` of 5,000 is derived from recall@K analysis across five gold-standard benchmark pairs. At K=5,000, the system captures 30–52% of known gold parallels depending on the text pair, with fused scores concentrated in the multi-channel convergence zone (score ≥ 3.5). This represents the point of diminishing returns for interactive browsing: results beyond rank 5,000 are predominantly single-channel matches with low confidence.

A score-based analysis reveals a natural structural break at fused_score ≈ 2.5–3.0, below which the result count jumps from ~7K to ~46K as single-channel noise dominates. For batch analysis or scholarly exhaustive search, a score-based threshold of ≥ 2.0 captures 38–56% of gold parallels while remaining computationally tractable.

See `evaluation/scripts/compute_recall_at_k.py` and `research/studies/fusion_experiment_phase1/` for the underlying data.

## References

- **Channel weights and recall figures**: `research/studies/fusion_experiment_phase1/publication/EVALUATION_REPORT.md`
- **V3 scoring algorithm**: Coffee et al. (2012), "Intertextuality in the Digital Age," *TAPA* 142.2
- **SPhilBERTa embeddings**: Riemenschneider & Frank (2023), "Exploring Large Language Models for Classical Philology"
- **Implementation**: `backend/fusion.py` (this document describes the design rationale for the code therein)
