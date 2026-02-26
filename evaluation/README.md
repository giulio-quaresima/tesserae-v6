# Tesserae V6 Evaluation Engine

Scripts and data for running intertext detection evaluation.

## Quick Start

```bash
cd ~/tesserae-v6-dev
source venv/bin/activate
TESSERAE_USE_DIRECT_SEARCH=1 python evaluation/scripts/run_all_channels_baseline.py
```

## Structure

- **scripts/** — Evaluation runners (baselines, fusion, precision, analysis)
- **benchmarks/** — Canonical gold standard benchmark files
- **syntax_baseline_data/** — Pre-computed syntax channel baseline data

## Results

Study results are saved in `research/studies/`. The latest report is always at `research/LATEST_REPORT.md`.

## Definitive Pipeline

```bash
tmux new-session -d -s eval "cd ~/tesserae-v6-dev && source venv/bin/activate && bash evaluation/scripts/run_definitive_pipeline.sh 2>&1; echo DONE; sleep 86400"
```

## Isolation from Website

Evaluation runs as standalone scripts using direct imports (`TESSERAE_USE_DIRECT_SEARCH=1`). It does not modify or run the dev website.
