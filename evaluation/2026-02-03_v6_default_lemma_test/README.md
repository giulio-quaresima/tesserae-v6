# V6 Default Pairwise Lemma Test

**Date:** February 3-4, 2026  
**Tesserae Version:** V6  
**Test Focus:** Default lemma matching for Latin texts

## Overview

This evaluation tests Tesserae V6's default pairwise lemma matching against two scholarly benchmarks:
- **Lucan-Vergil (bench41):** Bellum Civile Book 1 vs Aeneid
- **Valerius Flaccus:** Argonautica Book 1 vs Vergil

## Key Findings

| Finding | Result |
|---------|--------|
| Recall on valid lexical parallels | **100%** |
| Ranking quality (median rank) | 700-900 |
| Score ceiling ties | 21% of results |

## Folder Structure

```
2026-02-03_v6_default_lemma_test/
├── reports/                    # Documentation
│   ├── BENCHMARK_EVALUATION_REPORT.md   # Main report
│   ├── REPRODUCIBILITY_GUIDE.md         # Reproduction instructions
│   ├── RESEARCH_LOG.md                  # Detailed session log
│   └── VF_LINE_ALIGNMENT_REPORT.md      # VF corpus alignment notes
├── data/
│   ├── benchmarks/             # Original benchmark data
│   │   ├── lucan_vergil_benchmark.json
│   │   ├── lucan_vergil_lexical_benchmark.json
│   │   ├── vf_benchmark.json
│   │   └── vf_benchmark_aligned.json
│   ├── classification/         # Processed classification data
│   │   ├── vf_vergil_classified.json
│   │   ├── vf_line_alignment.json
│   │   └── vf_line_map.json
│   └── analysis/               # Error analysis files
│       ├── missed_lexical_parallels.json
│       ├── vf_missed_analysis.json
│       ├── vf_missed_lexical.json
│       └── vocab_mismatch_examples.json
└── scripts/                    # Reproduction scripts
    └── run_benchmark_tests.py
```

## Quick Start

1. Start Tesserae V6: `python main.py`
2. Run benchmark tests: `python scripts/run_benchmark_tests.py`
3. See `reports/REPRODUCIBILITY_GUIDE.md` for detailed instructions

## References

- Coffee et al. (2012). "Intertextuality in the Digital Age." TAPA 142(2): 383-422.
- Manjavacas et al. (2019). "A Statistical Approach to Detecting Textual Reuse."
