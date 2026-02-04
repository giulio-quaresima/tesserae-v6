# VF Benchmark Line Alignment Analysis

## Summary

Created alignment between VF Argonautica 1 lines in the Spaeth benchmark and the V6 corpus.

### Alignment Statistics
- **Total benchmark entries**: 945
- **Line corrections needed**: 66 entries (7%)
- **Unique lines with different numbering**: 43

### Offset Distribution
| Offset | Count | % |
|--------|-------|---|
| -2 | 1 | 0.1% |
| -1 | 21 | 2.3% |
| 0 | 865 | 92.9% |
| +1 | 39 | 4.2% |
| +2 | 5 | 0.5% |

## Key Finding

**92.9% of benchmark lines align correctly** with the V6 corpus. The line numbering discrepancies 
only affect 7% of entries, and the ±3 line tolerance used in evaluation already catches most of these.

## Specific Corrections

Lines where benchmark and corpus numbering differ:

| Benchmark Line | Corpus Line | Offset |
|----------------|-------------|--------|
| 11 | 13 | +2 |
| 13 | 11 | -2 |
| 28 | 29 | +1 |
| 104 | 105 | +1 |
| 126 | 127 | +1 |
| 135 | 136 | +1 |
| 142 | 143 | +1 |
| 232 | 233 | +1 |
| 490 | 491 | +1 |
| 548 | 549 | +1 |
| 620 | 621 | +1 |
| 637 | 638 | +1 |
| 682 | 683 | +1 |
| 822 | 823 | +1 |

## Example: Lines 11-13 Swap

The most notable correction is lines 11 and 13 which appear swapped:

- **Benchmark line 11** claims phrase "namque potes"
- **Corpus line 11** has: "sancte pater, veterumque fave veneranda canenti"
- **Corpus line 13** has: "namque potest, Solymo nigrantem pulvere fratrem"

This suggests either:
1. Different manuscript traditions
2. A typo in the original benchmark data
3. Different line numbering conventions (e.g., counting from proem vs. from dedication)

## Impact on Evaluation

The alignment corrections **do not significantly improve recall** because:
1. Most lines already match (92.9%)
2. The ±3 line tolerance catches shifted lines
3. Most "misses" are due to vocabulary mismatch, not line numbering

## Files Created

- `evaluation/vf_benchmark_aligned.json` - Benchmark with corrected line numbers
- `evaluation/vf_line_alignment.json` - Full alignment details
- `evaluation/vf_line_map.json` - Simple line number mapping

## Usage

To use the aligned benchmark:

```python
with open('evaluation/vf_benchmark_aligned.json') as f:
    benchmark = json.load(f)

for entry in benchmark:
    # Original benchmark line
    original_line = entry['source'].get('original_line_start')
    
    # Corrected line matching V6 corpus
    corpus_line = entry['source']['line_start']
    
    # Offset applied (0 if no correction)
    offset = entry['source'].get('alignment_offset', 0)
```
