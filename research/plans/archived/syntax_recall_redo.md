# Syntax Recall Evaluation: Full Redo

## Problem

Current implementation ranks only **gold source lines**. Correct design: for each target line, rank **all source lines** in the source work, take top K, combine with lemma. Simulates real search (lemma + syntax over full corpus).

## Fix

Replace `unique_source = set(e["source_ref"] for e in gold)` with:
```python
all_source_refs = SyntaxLatinDB.list_refs_for_work(source_pattern)
```

Files to modify:
- run_combined_recall_all_benchmarks.py
- extract_syntax_examples_all_benchmarks.py

## Computational Cost

| Benchmark | Targets | Source lines | Similarity computations |
|-----------|---------|--------------|-------------------------|
| Lucan–Vergil | ~213 | ~700 | ~150k |
| VF–Vergil | ~500 | ~600 | ~300k |
| Achilleid vs Vergil | ~314 | ~1100 | ~345k |

Expect ~5–15 min for full run.

## Note

Recall will likely **decrease** (gold harder to find in top K when competing with full corpus).
