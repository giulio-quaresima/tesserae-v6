#!/usr/bin/env python3
"""
Achilleid Benchmark Recall Test

Tests Tesserae V6 recall on the Geneva seminar Achilleid benchmark.
Uses consistent API parameters with Lucan-Vergil and VF tests.

Methodology:
1. Same API parameters (match_type=lemma, min_matches=2, no stoplist)
2. Quality filter: Type 4-5 (inferred from scholarly citations/notes)
3. Hit detection: Match on source book/line → target book/line

IMPORTANT LIMITATION:
Unlike bench41/VF, this benchmark lacks source text match words, so we 
CANNOT verify "truly lexical" (2+ shared lemmas) status for missed entries.
Results represent RAW RECALL on all scholar-attested parallels, not 
lexical-subset recall.

Author: Tesserae V6 Evaluation
Date: February 4, 2026
"""

import json
import requests
import time
from collections import defaultdict
from pathlib import Path

API_BASE = "http://localhost:5000/api"
BENCHMARK_PATH = Path(__file__).parent.parent / "data/benchmarks/achilleid_benchmark_classified.json"
OUTPUT_DIR = Path(__file__).parent.parent / "data/analysis"

WORK_MAPPING = {
    "statius.thebiad": "statius.thebaid.tess",
    "statius.thebaid": "statius.thebaid.tess",
    "vergil.aeneid": "vergil.aeneid.tess",
    "ovid.metamorphoses": "ovid.metamorphoses.tess",
    "ovid.heroides": "ovid.heroides.tess",
    "ovid.ars_amatoria": "ovid.ars_amatoria.tess",
    "ovid.amores": "ovid.amores.tess",
    "statius.achilleid": "statius.achilleid.tess",
    "ovid.remedia_amoris": "ovid.remedia_amoris.tess",
}

SEARCH_PARAMS = {
    "match_type": "lemma",
    "min_matches": 2,
    "stoplist_basis": "corpus",
    "stoplist_size": 0,
    "source_unit_type": "line",
    "target_unit_type": "line",
    "max_distance": 999,
    "max_results": 10000,
}

def load_benchmark():
    """Load the classified Achilleid benchmark."""
    with open(BENCHMARK_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_text_id(filename):
    """Get text ID from API."""
    resp = requests.get(f"{API_BASE}/texts")
    if resp.status_code != 200:
        return None
    texts = resp.json()
    if isinstance(texts, dict):
        texts = texts.get('texts', [])
    for t in texts:
        if t.get('filename') == filename or t.get('id') == filename:
            return t.get('id')
    return None

def run_search(source_id, target_id):
    """Run a Tesserae search."""
    params = SEARCH_PARAMS.copy()
    params['source'] = source_id
    params['target'] = target_id
    
    resp = requests.post(f"{API_BASE}/search", json=params)
    if resp.status_code != 200:
        return []
    result = resp.json()
    if isinstance(result, list):
        return result
    return result.get('results', [])

def extract_line_number(line_str):
    """Extract numeric line number from various formats.
    
    Formats handled:
    - "1_3" (book_line) -> 3
    - "stat. ach. 1.7" -> 7
    - "verg. aen. 10.816" -> 816
    - "7" -> 7
    """
    if not line_str:
        return None
    line_str = str(line_str).strip()
    
    # Handle underscore format: "1_3" -> 3
    if '_' in line_str:
        parts = line_str.split('_')
        line_str = parts[-1]
    
    # Handle ref format: "stat. ach. 1.7" or "verg. aen. 10.816"
    if '.' in line_str and ' ' in line_str:
        # Last part after last dot is the line number
        parts = line_str.split('.')
        line_str = parts[-1]
    
    try:
        return int(float(line_str))
    except:
        return None

def extract_book_line(line_str):
    """Extract (book, line) tuple from various formats."""
    if not line_str:
        return None, None
    line_str = str(line_str).strip()
    
    # Handle "1_3" format
    if '_' in line_str:
        parts = line_str.split('_')
        try:
            return int(parts[0]), int(parts[1])
        except:
            return None, None
    
    # Handle "stat. ach. 1.7" format
    if '.' in line_str:
        parts = line_str.split('.')
        if len(parts) >= 2:
            try:
                book = int(parts[-2].split()[-1])  # Get number before last dot
                line = int(parts[-1])
                return book, line
            except:
                pass
    
    return None, None

def check_lemma_overlap(entry, lemma_data):
    """Check if entry has true lexical overlap using lemmatization."""
    source_text = entry.get('source_text', '').lower()
    target_text = entry.get('target_text', '').lower()
    
    if not source_text or not target_text:
        return 0, []
    
    source_words = set(source_text.split())
    target_words = set(target_text.split())
    
    shared = source_words & target_words
    content_shared = [w for w in shared if len(w) > 2 and w not in {'et', 'in', 'ad', 'de', 'ex', 'ab', 'cum', 'pro', 'per', 'sub', 'non', 'nec', 'sed', 'que', 'atque', 'ac', 'aut', 'vel', 'sive', 'seu', 'nam', 'enim', 'ergo', 'igitur', 'tamen', 'autem', 'quidem', 'quoque'}]
    
    return len(content_shared), content_shared

def main():
    print("=" * 70)
    print("ACHILLEID BENCHMARK RECALL TEST")
    print("Methodology: Consistent with Lucan-Vergil and VF tests")
    print("=" * 70)
    
    benchmark = load_benchmark()
    entries = benchmark['entries']
    
    high_quality = [e for e in entries if e.get('assigned_type', 0) >= 4]
    print(f"\nTotal benchmark entries: {len(entries)}")
    print(f"High-quality (Type 4-5): {len(high_quality)}")
    
    source_text = "statius.achilleid.tess"
    source_id = get_text_id(source_text)
    if not source_id:
        print(f"ERROR: Could not find source text {source_text}")
        return
    print(f"\nSource: {source_text} (ID: {source_id})")
    
    by_target = defaultdict(list)
    for e in high_quality:
        target_work = e.get('source_work', '')
        corpus_file = WORK_MAPPING.get(target_work)
        if corpus_file:
            by_target[corpus_file].append(e)
        else:
            by_target['UNMAPPED'].append(e)
    
    print(f"\nTarget works in benchmark:")
    for target, entries_list in sorted(by_target.items(), key=lambda x: -len(x[1])):
        print(f"  {target}: {len(entries_list)} parallels")
    
    results_by_target = {}
    all_found = []
    all_missed = []
    all_skipped = []
    
    print("\n" + "-" * 70)
    print("Running searches...")
    print("-" * 70)
    
    for target_file, target_entries in by_target.items():
        if target_file == 'UNMAPPED':
            for e in target_entries:
                all_skipped.append({**e, 'skip_reason': 'Target work not in corpus'})
            continue
        
        target_id = get_text_id(target_file)
        if not target_id:
            print(f"  SKIP: {target_file} not found in corpus")
            for e in target_entries:
                all_skipped.append({**e, 'skip_reason': 'Target text not found'})
            continue
        
        print(f"\n  Searching: Achilleid → {target_file}")
        search_results = run_search(source_id, target_id)
        print(f"    V6 returned {len(search_results)} results")
        
        result_lines = {}  # (book, line, book, line) -> matched_words info
        for r in search_results:
            # V6 results have nested 'source' and 'target' objects with 'ref' field
            src_ref = r.get('source', {}).get('ref', '')
            tgt_ref = r.get('target', {}).get('ref', '')
            
            src_book, src_line = extract_book_line(src_ref)
            tgt_book, tgt_line = extract_book_line(tgt_ref)
            
            if src_line and tgt_line:
                # Store as (achilleid_line, target_line) with matched words info
                key = (src_book, src_line, tgt_book, tgt_line)
                matched_words = r.get('matched_words', [])
                lemma_count = len(matched_words)
                result_lines[key] = {
                    'lemma_count': lemma_count,
                    'matched_lemmas': [w.get('lemma', '') for w in matched_words],
                    'score': r.get('overall_score', 0)
                }
        
        found = 0
        missed = 0
        
        for entry in target_entries:
            # Benchmark terminology (reversed from V6):
            # Benchmark TARGET = Achilleid = V6 source
            # Benchmark SOURCE = Vergil/etc = V6 target
            bench_achilleid_book, bench_achilleid_line = extract_book_line(entry.get('target_line'))
            bench_target_book, bench_target_line = extract_book_line(entry.get('source_line'))
            
            if bench_achilleid_line is None or bench_target_line is None:
                all_skipped.append({**entry, 'skip_reason': 'Invalid line numbers'})
                continue
            
            # Check if this parallel exists in V6 results (matching Achilleid line to target line)
            key = (bench_achilleid_book, bench_achilleid_line, bench_target_book, bench_target_line)
            match_info = result_lines.get(key, None)
            is_found = match_info is not None
            
            # Use V6's actual lemma count if found
            if is_found:
                lemma_count = match_info['lemma_count']
                matched_lemmas = match_info['matched_lemmas']
                score = match_info['score']
            else:
                lemma_count = 0
                matched_lemmas = []
                score = 0
            
            entry_result = {
                **entry,
                'found': is_found,
                'lemma_count': lemma_count,
                'matched_lemmas': matched_lemmas,
                'v6_score': score,
                'target_file': target_file
            }
            
            if is_found:
                found += 1
                all_found.append(entry_result)
            else:
                missed += 1
                all_missed.append(entry_result)
        
        results_by_target[target_file] = {
            'total': len(target_entries),
            'found': found,
            'missed': missed,
            'v6_results': len(search_results)
        }
        
        print(f"    Found: {found}/{len(target_entries)} ({round(found/len(target_entries)*100,1) if target_entries else 0}%)")
        
        time.sleep(0.5)
    
    print("\n" + "=" * 70)
    print("SUMMARY RESULTS")
    print("=" * 70)
    
    total_tested = len(all_found) + len(all_missed)
    total_found = len(all_found)
    
    print(f"\nOverall High-Quality (Type 4-5) Recall:")
    print(f"  Tested: {total_tested}")
    print(f"  Found: {total_found}")
    print(f"  Missed: {len(all_missed)}")
    print(f"  Skipped: {len(all_skipped)}")
    print(f"  Raw Recall: {round(total_found/total_tested*100,1) if total_tested else 0}%")
    
    # For found entries, we have actual lemma counts from V6
    # All found entries by definition have 2+ lemmas (that's our min_matches setting)
    truly_lexical_found = [e for e in all_found if e.get('lemma_count', 0) >= 2]
    
    print(f"\nTruly Lexical Analysis (2+ shared lemmas):")
    print(f"  Found with 2+ lemmas: {len(truly_lexical_found)} (100% of found, by definition)")
    print(f"  Missed parallels: {len(all_missed)} (unknown lemma overlap - not in results)")
    print(f"  NOTE: Without full lemmatization of missed entries, we cannot calculate true lexical recall")
    
    print(f"\nBy Target Work:")
    print("-" * 50)
    for target, stats in sorted(results_by_target.items(), key=lambda x: -x[1]['total']):
        pct = round(stats['found']/stats['total']*100,1) if stats['total'] else 0
        print(f"  {target}: {stats['found']}/{stats['total']} ({pct}%)")
    
    # Analyze missed parallels by type and notes
    missed_by_type = {5: 0, 4: 0, 3: 0, 2: 0, 0: 0}
    for m in all_missed:
        t = m.get('assigned_type', 0)
        missed_by_type[t] = missed_by_type.get(t, 0) + 1
    
    found_by_type = {5: 0, 4: 0, 3: 0, 2: 0, 0: 0}
    for f in all_found:
        t = f.get('assigned_type', 0)
        found_by_type[t] = found_by_type.get(t, 0) + 1
    
    print(f"\nRecall by Assigned Type:")
    print("-" * 50)
    for t in [5, 4, 3, 2, 0]:
        total = found_by_type.get(t, 0) + missed_by_type.get(t, 0)
        if total > 0:
            pct = round(found_by_type.get(t, 0) / total * 100, 1)
            print(f"  Type {t}: {found_by_type.get(t, 0)}/{total} ({pct}%)")
    
    output = {
        'metadata': {
            'test_date': time.strftime('%Y-%m-%d'),
            'benchmark': 'Achilleid Book 1 (Geneva 2015)',
            'methodology': 'Consistent with Lucan-Vergil and VF tests',
            'search_params': SEARCH_PARAMS
        },
        'summary': {
            'high_quality_tested': total_tested,
            'found': total_found,
            'missed': len(all_missed),
            'skipped': len(all_skipped),
            'raw_recall_pct': round(total_found/total_tested*100,1) if total_tested else 0,
            'found_by_type': found_by_type,
            'missed_by_type': missed_by_type
        },
        'by_target': results_by_target,
        'found_entries': all_found[:50],
        'missed_entries': all_missed,
        'skipped_entries': all_skipped
    }
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / 'achilleid_recall_results.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {output_path}")

if __name__ == '__main__':
    main()
