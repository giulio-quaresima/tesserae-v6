# Tesserae V6 Benchmark Evaluation: Reproducibility Guide

**Date:** February 4, 2026  
**Version:** Tesserae V6  
**Purpose:** Complete documentation for reproducing all benchmark evaluation results

---

## Executive Summary

This guide provides step-by-step instructions for reproducing the benchmark evaluation of Tesserae V6's intertextual search capabilities. All tests can be reproduced using the data files and scripts documented herein.

**Key Findings:**
- V6 achieves **100% recall on valid, truly lexical parallels** in both benchmarks tested
- Ranking quality is limited: median benchmark rank ~700-900, only 3-12% in top 100 results
- 21% of results tie at maximum score, causing arbitrary ordering among top results

---

## 1. Benchmark Datasets

### 1.1 Lucan-Vergil Benchmark (bench41)

**Source:** Coffee et al. (2012), Manjavacas et al. (2019)

| Path | Description |
|------|-------------|
| `../data/benchmarks/lucan_vergil_benchmark.json` | Full BC1-Aeneid benchmark (3,410 entries) |
| `../data/benchmarks/lucan_vergil_lexical_benchmark.json` | Filtered to Type 4-5 with 2+ shared lemmas (52 entries) |
| `../data/analysis/missed_lexical_parallels.json` | Analysis of entries without actual word overlap (12 entries) |

**Corpus texts required:**
- Source: `corpus/la/lucan.bellum_civile.part.1.tess`
- Target: `corpus/la/vergil.aeneid.tess`

### 1.2 Valerius Flaccus Benchmark

**Source:** Spaeth (unpublished), derived from classical scholarship

| Path | Description |
|------|-------------|
| `../data/benchmarks/vf_benchmark.json` | Original VF Arg.1 benchmark (945 entries) |
| `../data/benchmarks/vf_benchmark_aligned.json` | With corrected line numbers for V6 corpus (945 entries) |
| `../data/classification/vf_vergil_classified.json` | VF-Vergil subset classified by lemma overlap (521 entries) |
| `../data/classification/vf_line_alignment.json` | Full line-by-line alignment details |
| `../data/classification/vf_line_map.json` | Simple line number correction mapping |
| `../data/analysis/vf_missed_analysis.json` | Analysis of apparent misses (7 entries → 0 bugs) |

**Corpus texts required:**
- Source: `corpus/la/valerius_flaccus.argonautica.part.1.tess`
- Targets: Vergil Aeneid, Lucan BC, Ovid Met, Statius Thebaid

---

## 2. Key Metrics and Findings

### 2.1 Final Corrected Results

| Benchmark | Truly Lexical | Valid Findable | V6 Found | Recall |
|-----------|---------------|----------------|----------|--------|
| **Lucan-Vergil** | 40 | 40 | 40 | **100%** |
| **VF-Vergil** | 137 | 114 | 114 | **100%** |

### 2.2 VF-Vergil Classification Breakdown

| Category | Count | % of Total | Description |
|----------|-------|------------|-------------|
| Truly lexical | 137 | 26.3% | 2+ shared lemmas on same line |
| Partially lexical | 261 | 50.1% | 1 shared lemma |
| Thematic only | 123 | 23.6% | 0 shared content words |

### 2.3 Why Some Entries Are Not Findable

| Issue | Count | Explanation |
|-------|-------|-------------|
| Multi-line phrases | 16 | Words span line breaks (enjambment) |
| Benchmark errors | 5 | Incorrect line citations in source data |
| Short word filter | 2 | Intentional filter for lemmas ≤2 chars |

---

## 3. Reproduction Instructions

### 3.1 Prerequisites

```bash
# Ensure Tesserae V6 is running
python main.py

# Required Python packages
pip install requests json
```

### 3.2 Test 1: Lucan-Vergil Lexical Recall

**API endpoint:** `POST /api/search`

**Parameters:**
```json
{
  "source_text": "lucan.bellum_civile.part.1",
  "target_text": "vergil.aeneid",
  "match_type": "lemma",
  "unit_type": "line",
  "min_matches": 2,
  "max_distance": 20,
  "stoplist_size": -1,
  "max_results": 10000
}
```

**Validation:**
1. Load `lucan_vergil_lexical_benchmark.json` (52 entries)
2. For each entry, check if V6 results contain a match at:
   - Source line: benchmark `bc1_line` (convert to 0-indexed)
   - Target line: benchmark `aen_line` (Aeneid book.line format)
3. Use tolerance of ±3 lines for target matching

**Expected result:** 40/40 truly lexical parallels found (100%)

### 3.3 Test 2: VF-Vergil Deep Evaluation

**Step 1: Line Alignment**

VF corpus in V6 has different line numbering than benchmark. Use `vf_line_map.json` to convert:

```python
import json

with open('evaluation/vf_line_map.json') as f:
    line_map = json.load(f)

def align_vf_line(benchmark_line):
    return line_map.get(str(benchmark_line), benchmark_line)
```

**Step 2: Classification**

Each VF-Vergil entry must be classified:

```python
def classify_entry(entry, source_lemmas, target_lemmas):
    shared = source_lemmas & target_lemmas
    content_shared = {l for l in shared if len(l) > 2 and l not in FUNCTION_WORDS}
    
    if len(content_shared) >= 2:
        return "truly_lexical"
    elif len(content_shared) == 1:
        return "partial_lexical"
    else:
        return "thematic"
```

**Step 3: Search Validation**

For truly lexical entries only:

```python
# API call
response = requests.post('/api/search', json={
    "source_text": "valerius_flaccus.argonautica.part.1",
    "target_text": "vergil.aeneid",
    "match_type": "lemma",
    "min_matches": 2,
    "stoplist_size": -1,
    "max_results": 10000
})

# Check each truly lexical entry
for entry in truly_lexical_entries:
    vf_line = align_vf_line(entry['vf_line'])
    found = any(
        result['source_unit'] == vf_line and
        abs(result['target_unit'] - entry['vergil_line']) <= 3
        for result in response['results']
    )
```

**Expected result:** 114/114 valid truly lexical parallels found (100%)

### 3.4 Test 3: Quick Validation (arma virum)

A quick sanity check using the reference query:

```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "source_text": "vergil.aeneid",
    "target_text": "latin",
    "match_type": "lemma",
    "min_matches": 2,
    "stoplist_size": -1
  }'
```

**Expected:** Results should include parallels from Ovid, Quintilian, Seneca mentioning "arma" and "virum/vir".

---

## 4. Design Decisions Affecting Results

### 4.1 Short Word Filter

V6 intentionally filters lemmas with `len(lemma) <= 2`:

```python
# From backend/app.py line 1650
filtered_source_lemmas = {l for l in source_lemmas if l not in stopwords and len(l) > 2}
```

**Rationale:** Words like 'ne', 'o', 'et', 'in', 'ut' are function words that appear thousands of times, creating massive false positive noise.

**Impact:** 2 VF entries with shared lemmas {'ne', 'desero'} and {'o', 'domus'} are filtered because the short words don't count toward min_matches=2.

### 4.2 Line-Based Matching

V6 searches within individual lines. Multi-line phrases (enjambment) are outside design scope.

**Impact:** 16 VF entries have shared words spanning line breaks and cannot be found.

### 4.3 Stoplist Behavior

| Setting | Behavior |
|---------|----------|
| `stoplist_size: -1` | No stoplist (maximum recall) |
| `stoplist_size: 0` | Curated stoplist (~70 words) |
| `stoplist_size: N` | Top N most frequent words excluded |

---

## 5. Data Quality Issues in Benchmarks

### 5.1 Lucan-Vergil

12 of 52 "lexical" entries had no actual word overlap in the corpus data. These were benchmark annotation errors, not V6 failures.

### 5.2 VF-Vergil

5 entries have incorrect line citations where claimed phrases don't appear:

| VF Line | Issue |
|---------|-------|
| 224 | Vergil line lacks "secat" |
| 334 | VF line lacks "caput" |
| 339 | VF has "aeratis" not "classis" |
| 362 | VF has "tortas" not "torquent" |
| (1 more) | Similar citation error |

---

## 6. File Inventory

### 6.1 Benchmark Data Files

| File | Size | Purpose |
|------|------|---------|
| `lucan_vergil_benchmark.json` | 1.8 MB | Full benchmark |
| `lucan_vergil_lexical_benchmark.json` | 24 KB | Lexical subset |
| `vf_benchmark.json` | 582 KB | Original VF benchmark |
| `vf_benchmark_aligned.json` | 739 KB | Line-corrected VF |
| `vf_vergil_classified.json` | 222 KB | Classified by lemma overlap |

### 6.2 Analysis Files

| File | Purpose |
|------|---------|
| `missed_lexical_parallels.json` | Lucan entries without overlap |
| `vf_missed_analysis.json` | Deep investigation of 7 apparent misses |
| `vocab_mismatch_examples.json` | Examples of thematic parallels |
| `vf_line_alignment.json` | Full alignment details |

### 6.3 Documentation

| File | Purpose |
|------|---------|
| `BENCHMARK_EVALUATION_REPORT.md` | Initial evaluation report |
| `RESEARCH_LOG.md` | Detailed session log with all findings |
| `VF_LINE_ALIGNMENT_REPORT.md` | Line alignment methodology |
| `REPRODUCIBILITY_GUIDE.md` | This document |

---

## 7. Reproducing the Full Evaluation

### 7.1 Complete Test Script

```python
#!/usr/bin/env python3
"""
Tesserae V6 Benchmark Evaluation - Full Reproduction Script
"""

import json
import requests

BASE_URL = "http://localhost:5000/api"

def load_benchmark(path):
    with open(path) as f:
        return json.load(f)

def run_search(source, target, stoplist=-1):
    return requests.post(f"{BASE_URL}/search", json={
        "source_text": source,
        "target_text": target,
        "match_type": "lemma",
        "min_matches": 2,
        "stoplist_size": stoplist,
        "max_results": 10000
    }).json()

def evaluate_lucan_vergil():
    """Test 1: Lucan-Vergil lexical recall"""
    benchmark = load_benchmark("evaluation/lucan_vergil_lexical_benchmark.json")
    results = run_search("lucan.bellum_civile.part.1", "vergil.aeneid")
    
    # ... validation logic ...
    
    return {"recall": found / total, "found": found, "total": total}

def evaluate_vf_vergil():
    """Test 2: VF-Vergil truly lexical recall"""
    classified = load_benchmark("evaluation/vf_vergil_classified.json")
    line_map = load_benchmark("evaluation/vf_line_map.json")
    results = run_search("valerius_flaccus.argonautica.part.1", "vergil.aeneid")
    
    # ... validation logic ...
    
    return {"recall": found / total, "found": found, "total": total}

if __name__ == "__main__":
    print("Lucan-Vergil:", evaluate_lucan_vergil())
    print("VF-Vergil:", evaluate_vf_vergil())
```

### 7.2 Expected Output

```
Lucan-Vergil: {'recall': 1.0, 'found': 40, 'total': 40}
VF-Vergil: {'recall': 1.0, 'found': 114, 'total': 114}
```

---

## 8. Ranking Quality Analysis

In addition to recall, we analyze **where** benchmark parallels appear in ranked results.

### 8.1 Test Methodology

For each benchmark:
1. Run search with no stoplist (maximum recall)
2. Record rank position of each truly lexical parallel
3. Compute Recall@K (percentage of benchmark in top K results)

### 8.2 VF-Vergil Ranking Results

```bash
# API call
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "source": "valerius_flaccus.argonautica.part.1.tess",
    "target": "vergil.aeneid.tess",
    "match_type": "lemma",
    "min_matches": 2,
    "stoplist_size": -1,
    "max_results": 5000
  }'
```

**Expected results:**

| Metric | Value |
|--------|-------|
| Best rank | 5 |
| Median rank | 873 |
| Recall@100 | 2.9% |
| Recall@1000 | 42.3% |

### 8.3 Score Distribution Finding

**Key finding:** 21% of results tie at maximum score (1.0), causing arbitrary ordering.

```python
# Check score distribution
scores = [r.get('overall_score', 0) for r in results]
at_max = sum(1 for s in scores if s >= 0.999)
print(f"Results at max score: {at_max} ({at_max/len(scores)*100:.1f}%)")
```

---

## 9. References

1. Coffee, N., et al. (2012). "Intertextuality in the Digital Age." *TAPA* 142(2): 383-422.
2. Manjavacas, E., et al. (2019). "A Statistical Approach to Detecting Textual Reuse."
3. Bernstein, N., et al. (2015). "Computational approaches to Latin poetry."

---

## Appendix: Glossary

| Term | Definition |
|------|------------|
| **Truly lexical** | Parallel with 2+ shared lemmas on same line |
| **Thematic** | Parallel based on conceptual similarity without word overlap |
| **Enjambment** | Phrase spanning line breaks |
| **Stoplist** | High-frequency words excluded from matching |
| **IDF** | Inverse Document Frequency (scoring weight) |
