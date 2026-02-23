# Combined Lemma + Syntax Recall Plan

## Goal

Show that **lemma ∪ syntax** yields higher total recall than either channel alone.

## Evaluation Logic

- **Lemma found:** (L,V) appears in lemma API results with ±3 line tolerance
- **Syntax found:** L is in top K of source lines ranked by structural similarity to V
- **Combined found:** lemma_found OR syntax_found
- **Combined recall** = |combined_found| / |gold|

## Overlap Breakdown

|  | Syntax found | Syntax not found |
|--|--------------|------------------|
| **Lemma found** | Both | Lemma only |
| **Lemma not found** | Syntax only | Neither |

## Implementation

New script: `evaluation/scripts/run_combined_recall_study.py`

1. Load gold from lucan_vergil_lexical_benchmark.json
2. Lemma channel: run_search() with lemma, max_results=10000
3. Syntax channel: For each target V, rank all source lines by compute_structural_similarity; syntax_found = L in ranked[:K]
4. K for syntax: 50, 100, 500
5. Output: combined_recall_report.md, combined_recall_metrics.csv

## Dependencies

- syntax_latin.db
- run_evaluation.refs_match, gold_found_in
