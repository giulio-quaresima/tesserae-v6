#!/usr/bin/env python3
"""
Full Default Evaluation: Lucan BC1 vs All Vergil Aeneid Books

Tests V6 with ACTUAL DEFAULT SETTINGS to establish honest baseline performance.

V6 Defaults (from backend/config.py and app.py):
- match_type: lemma
- min_matches: 2
- max_distance: 20 (poetry default, auto-adjusted from 999)
- max_results: 500
- stoplist_size: 0 (no stoplist)
- stoplist_basis: source_target
- unit_type: line
"""

import json
import requests
import os
import sys
from datetime import datetime

API_BASE = os.environ.get('API_BASE', 'http://localhost:5000')

V6_DEFAULTS = {
    'match_type': 'lemma',
    'min_matches': 2,
    'max_distance': 20,
    'max_results': 500,
    'stoplist_size': 0,
    'stoplist_basis': 'source_target',
    'source_unit_type': 'line',
    'target_unit_type': 'line'
}

def load_benchmark(filepath='evaluation/lucan_vergil_benchmark.json'):
    with open(filepath, 'r') as f:
        return json.load(f)

def parse_v6_ref(ref_str):
    """Parse V6 reference like 'luc. 1.13' or 'verg. aen. 1.368'"""
    parts = ref_str.split('.')
    if len(parts) >= 2:
        try:
            line = int(parts[-1])
            book = int(parts[-2]) if len(parts) >= 2 else 1
            return (book, line)
        except ValueError:
            pass
    return (None, None)

def run_search(source_text, target_text, settings):
    """Run a V6 pairwise search via API."""
    url = f"{API_BASE}/api/search"
    
    payload = {
        'source': source_text,
        'target': target_text,
        'language': 'la',
        'settings': settings
    }
    
    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
        return None

def find_benchmark_match(v6_result, benchmark, tolerance=2):
    """Check if a V6 result matches any benchmark parallel."""
    source_ref = v6_result.get('source', {}).get('ref', '')
    target_ref = v6_result.get('target', {}).get('ref', '')
    
    v6_source_book, v6_source_line = parse_v6_ref(source_ref)
    v6_target_book, v6_target_line = parse_v6_ref(target_ref)
    
    if v6_source_line is None or v6_target_line is None:
        return None
    
    for parallel in benchmark:
        bench_source_line = parallel['source'].get('line', 0)
        bench_target_book = parallel['target'].get('book', 0)
        bench_target_line = parallel['target'].get('line', 0)
        
        source_match = abs(v6_source_line - bench_source_line) <= tolerance
        target_book_match = v6_target_book == bench_target_book
        target_line_match = abs(v6_target_line - bench_target_line) <= tolerance
        
        if source_match and target_book_match and target_line_match:
            return parallel
    
    return None

def calculate_metrics(v6_results, benchmark, k_values=[10, 25, 50, 100, 200, 500]):
    """Calculate precision@K and recall@K metrics."""
    metrics = {}
    
    matches_found = []
    for i, result in enumerate(v6_results):
        match = find_benchmark_match(result, benchmark)
        matches_found.append((i, result, match))
    
    for k in k_values:
        if k > len(v6_results):
            continue
        top_k = matches_found[:k]
        hits = sum(1 for _, _, match in top_k if match is not None)
        
        precision = hits / k if k > 0 else 0
        recall = hits / len(benchmark) if len(benchmark) > 0 else 0
        
        metrics[f'precision@{k}'] = precision
        metrics[f'recall@{k}'] = recall
        metrics[f'hits@{k}'] = hits
    
    total_hits = sum(1 for _, _, match in matches_found if match is not None)
    metrics['total_hits'] = total_hits
    metrics['total_recall'] = total_hits / len(benchmark) if len(benchmark) > 0 else 0
    
    return metrics, matches_found

def main():
    print("=" * 70)
    print("FULL DEFAULT EVALUATION: Lucan BC1 vs Vergil Aeneid (All Books)")
    print("=" * 70)
    print(f"\nTimestamp: {datetime.now().isoformat()}")
    print("\nV6 Default Settings Being Tested:")
    for key, value in V6_DEFAULTS.items():
        print(f"  {key}: {value}")
    
    benchmark = load_benchmark()
    
    bc1_benchmark = [p for p in benchmark if p['source'].get('book') == 1]
    bc1_high = [p for p in bc1_benchmark if isinstance(p.get('relevance_type'), int) and p['relevance_type'] >= 4]
    bc1_medium = [p for p in bc1_benchmark if isinstance(p.get('relevance_type'), int) and p['relevance_type'] >= 3]
    
    print(f"\nBenchmark Statistics:")
    print(f"  Total BC1 parallels: {len(bc1_benchmark)}")
    print(f"  High-quality (Type 4-5): {len(bc1_high)}")
    print(f"  Medium+ (Type 3-5): {len(bc1_medium)}")
    
    all_results = []
    
    print("\n" + "-" * 70)
    print("Running V6 searches against all 12 Aeneid books...")
    print("-" * 70)
    
    for aen_book in range(1, 13):
        target = f'vergil.aeneid.part.{aen_book}.tess'
        print(f"  Searching BC1 vs Aeneid {aen_book}...", end=" ", flush=True)
        
        result = run_search(
            'lucan.bellum_civile.part.1.tess',
            target,
            V6_DEFAULTS
        )
        
        if result and 'results' in result:
            book_results = result['results']
            for r in book_results:
                r['_aeneid_book'] = aen_book
            all_results.extend(book_results)
            print(f"{len(book_results)} results")
        else:
            print("ERROR")
    
    all_results.sort(key=lambda x: x.get('overall_score', 0), reverse=True)
    
    print(f"\nTotal V6 results: {len(all_results)}")
    
    print("\n" + "-" * 70)
    print("Calculating metrics against full BC1 benchmark...")
    print("-" * 70)
    
    metrics, matches_found = calculate_metrics(all_results, bc1_benchmark)
    
    print("\n" + "=" * 70)
    print("EVALUATION RESULTS - V6 WITH DEFAULT SETTINGS")
    print("=" * 70)
    print(f"\nBenchmark: {len(bc1_benchmark)} parallels (BC1 vs all Aeneid)")
    print(f"V6 Results: {len(all_results)} total")
    print()
    
    print("Precision @ K (of top K results, how many are in benchmark?):")
    for k in [10, 25, 50, 100, 200, 500]:
        if f'precision@{k}' in metrics:
            print(f"  P@{k}: {metrics[f'precision@{k}']:.1%} ({metrics[f'hits@{k}']} hits)")
    
    print()
    print("Recall @ K (of benchmark parallels, how many found in top K?):")
    for k in [10, 25, 50, 100, 200, 500]:
        if f'recall@{k}' in metrics:
            print(f"  R@{k}: {metrics[f'recall@{k}']:.1%}")
    
    print(f"\nTotal Recall: {metrics['total_recall']:.1%} ({metrics['total_hits']} of {len(bc1_benchmark)} benchmark parallels found)")
    
    high_hits = sum(1 for _, result, match in matches_found if match and match.get('relevance_type', 0) >= 4)
    print(f"High-Quality Recall: {high_hits}/{len(bc1_high)} Type 4-5 parallels found ({high_hits/len(bc1_high)*100:.1f}%)")
    
    print("\n" + "-" * 70)
    print("Sample Verified Matches (V6 result matched to benchmark)")
    print("-" * 70)
    
    count = 0
    for i, result, match in matches_found:
        if match and count < 5:
            source = result.get('source', {})
            target = result.get('target', {})
            matched = result.get('matched_words', [])
            lemmas = [m.get('lemma', '') for m in matched]
            
            print(f"\n  Match #{count+1} (V6 rank: {i+1}, Type {match.get('relevance_type', '?')})")
            print(f"    {source.get('ref', '?')}: {source.get('text', '')[:60]}...")
            print(f"    {target.get('ref', '?')}: {target.get('text', '')[:60]}...")
            print(f"    Lemmas: {lemmas}")
            count += 1
    
    output = {
        'timestamp': datetime.now().isoformat(),
        'settings': V6_DEFAULTS,
        'benchmark_size': len(bc1_benchmark),
        'high_quality_size': len(bc1_high),
        'v6_results_count': len(all_results),
        'metrics': metrics,
        'methodology': {
            'source': 'Lucan Bellum Civile Book 1',
            'target': 'Vergil Aeneid (all 12 books)',
            'benchmark': 'bench41.txt parsed to JSON',
            'matching_tolerance': '±2 lines',
            'reference': 'Per Coffee et al. 2012, Bernstein et al. 2015'
        }
    }
    
    output_file = 'evaluation/full_default_evaluation_results.json'
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n\nResults saved to {output_file}")
    
    print("\n" + "=" * 70)
    print("METHODOLOGY NOTES")
    print("=" * 70)
    print("""
This evaluation follows established methodology from:
- Coffee et al. 2012 "Intertextuality in the Digital Age"
- Bernstein et al. 2015 "Comparative rates of text reuse"
- Manjavacas et al. 2019 "Automated Detection of Allusive Text Reuse"

The benchmark (bench41.txt) contains hand-ranked parallels with Type 1-5 scores.
Type 4-5 are high-confidence scholarly parallels.

Metrics:
- Precision@K: Of top K results, what fraction appears in benchmark?
- Recall@K: Of all benchmark parallels, what fraction found in top K?
- Line tolerance of ±2 used for matching (standard practice)
""")

if __name__ == '__main__':
    main()
