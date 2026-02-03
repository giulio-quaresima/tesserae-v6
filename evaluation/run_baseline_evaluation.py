#!/usr/bin/env python3
"""
Baseline Evaluation: Lucan BC1 vs Vergil Aeneid
Compare V6 search results against the bench41 benchmark.

This is a small-scale test to verify the evaluation pipeline works.
"""

import json
import requests
import os
import sys

API_BASE = os.environ.get('API_BASE', 'http://localhost:5000')

def load_benchmark(filepath='evaluation/lucan_vergil_benchmark.json'):
    """Load parsed benchmark data."""
    with open(filepath, 'r') as f:
        return json.load(f)

def filter_benchmark_by_type(benchmark, min_type=3):
    """Filter benchmark to only include high-relevance parallels."""
    return [p for p in benchmark if isinstance(p.get('relevance_type'), int) and p['relevance_type'] >= min_type]

def run_search(source_text, target_text, max_results=100):
    """Run a V6 pairwise search via API."""
    url = f"{API_BASE}/api/search"
    
    payload = {
        'source': source_text,
        'target': target_text,
        'language': 'la',
        'settings': {
            'match_type': 'lemma',
            'min_matches': 2,
            'max_distance': 10,
            'stoplist_size': 10,
            'stoplist_basis': 'corpus',
            'source_unit_type': 'line',
            'target_unit_type': 'line',
            'max_results': max_results
        }
    }
    
    print(f"Running search: {source_text} vs {target_text}")
    print(f"Parameters: min_matches=2, max_distance=10, max_results={max_results}")
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
        return None

def normalize_location(work, book, line):
    """Normalize location for comparison."""
    return (str(book), int(line) if isinstance(line, int) else int(str(line).split('-')[0]))

def parse_v6_ref(ref_str):
    """
    Parse V6 reference like 'luc. 1.13' or 'verg. aen. 1.368'
    Returns (book, line) tuple.
    """
    import re
    parts = ref_str.split('.')
    if len(parts) >= 2:
        try:
            line = int(parts[-1])
            book = int(parts[-2]) if len(parts) >= 2 else 1
            return (book, line)
        except ValueError:
            pass
    return (None, None)

def find_benchmark_match(v6_result, benchmark, tolerance=2):
    """
    Check if a V6 result matches any benchmark parallel.
    Uses line number tolerance for fuzzy matching.
    """
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

def calculate_metrics(v6_results, benchmark, k_values=[10, 25, 50, 100]):
    """Calculate precision@K and recall@K metrics."""
    metrics = {}
    
    matches_found = []
    for i, result in enumerate(v6_results):
        match = find_benchmark_match(result, benchmark)
        matches_found.append((i, result, match))
    
    for k in k_values:
        top_k = matches_found[:k]
        hits = sum(1 for _, _, match in top_k if match is not None)
        
        precision = hits / k if k > 0 else 0
        recall = hits / len(benchmark) if len(benchmark) > 0 else 0
        
        metrics[f'precision@{k}'] = precision
        metrics[f'recall@{k}'] = recall
        metrics[f'hits@{k}'] = hits
    
    return metrics, matches_found

def display_sample_matches(matches_found, limit=5):
    """Display sample matches for verification."""
    print("\n" + "=" * 60)
    print("SAMPLE MATCHES (V6 result matched to benchmark)")
    print("=" * 60)
    
    count = 0
    for i, result, match in matches_found:
        if match and count < limit:
            source = result.get('source', {})
            target = result.get('target', {})
            matched = result.get('matched_words', [])
            lemmas = [m.get('lemma', '') for m in matched]
            
            print(f"\n--- Match #{count+1} (V6 rank: {i+1}) ---")
            print(f"V6 Source: {source.get('ref', '?')}")
            print(f"  Text: {source.get('text', '')[:80]}...")
            print(f"V6 Target: {target.get('ref', '?')}")
            print(f"  Text: {target.get('text', '')[:80]}...")
            print(f"Matched lemmas: {lemmas}")
            print(f"V6 Score: {result.get('overall_score', 'N/A')}")
            print(f"Benchmark Type: {match.get('relevance_type', 'N/A')}")
            count += 1
    
    if count == 0:
        print("\nNo matches found between V6 results and benchmark.")

def display_sample_misses(matches_found, limit=5):
    """Display sample V6 results that didn't match benchmark."""
    print("\n" + "=" * 60)
    print("SAMPLE NON-MATCHES (V6 found, not in benchmark)")
    print("=" * 60)
    
    count = 0
    for i, result, match in matches_found:
        if match is None and count < limit:
            source = result.get('source', {})
            target = result.get('target', {})
            matched = result.get('matched_words', [])
            lemmas = [m.get('lemma', '') for m in matched]
            
            print(f"\n--- V6 Result #{i+1} ---")
            print(f"Source: {source.get('ref', '?')}")
            print(f"  Text: {source.get('text', '')[:80]}...")
            print(f"Target: {target.get('ref', '?')}")
            print(f"  Text: {target.get('text', '')[:80]}...")
            print(f"Matched lemmas: {lemmas}")
            print(f"Score: {result.get('overall_score', 'N/A')}")
            count += 1

def main():
    print("=" * 60)
    print("BASELINE EVALUATION: Lucan BC1 vs Vergil Aeneid")
    print("=" * 60)
    
    benchmark = load_benchmark()
    print(f"\nLoaded benchmark: {len(benchmark)} total parallels")
    
    high_quality = filter_benchmark_by_type(benchmark, min_type=4)
    print(f"High-quality parallels (Type 4-5): {len(high_quality)}")
    
    medium_quality = filter_benchmark_by_type(benchmark, min_type=3)
    print(f"Medium+ parallels (Type 3-5): {len(medium_quality)}")
    
    bc1_benchmark = [p for p in benchmark if p['source'].get('book') == 1]
    print(f"Lucan BC Book 1 only: {len(bc1_benchmark)} parallels")
    
    bc1_aen1_benchmark = [p for p in bc1_benchmark if p['target'].get('book') == 1]
    print(f"BC1 vs Aeneid 1 only: {len(bc1_aen1_benchmark)} parallels")
    
    bc1_high = [p for p in bc1_benchmark if isinstance(p.get('relevance_type'), int) and p['relevance_type'] >= 4]
    print(f"BC1 high-quality (Type 4-5): {len(bc1_high)} parallels")
    
    bc1_aen1_high = [p for p in bc1_aen1_benchmark if isinstance(p.get('relevance_type'), int) and p['relevance_type'] >= 4]
    print(f"BC1 vs Aen1 high-quality: {len(bc1_aen1_high)} parallels")
    
    print("\n" + "-" * 60)
    print("Running V6 search (this may take a moment)...")
    print("-" * 60)
    
    search_result = run_search(
        source_text='lucan.bellum_civile.part.1.tess',
        target_text='vergil.aeneid.part.1.tess',
        max_results=100
    )
    
    if search_result is None:
        print("Search failed. Check that the server is running.")
        return
    
    if 'error' in search_result:
        print(f"Search error: {search_result['error']}")
        return
    
    results = search_result.get('results', [])
    print(f"\nV6 returned {len(results)} results")
    
    print("\n" + "-" * 60)
    print("Calculating metrics against BC1 vs Aen1 benchmark...")
    print("-" * 60)
    
    metrics, matches_found = calculate_metrics(results, bc1_aen1_benchmark)
    
    print("\n=== EVALUATION RESULTS ===")
    print(f"Benchmark size (BC1 vs Aen1): {len(bc1_aen1_benchmark)} parallels")
    print(f"High-quality subset: {len(bc1_aen1_high)} parallels (Type 4-5)")
    print()
    
    for k in [10, 25, 50, 100]:
        if f'precision@{k}' in metrics:
            print(f"Precision@{k}: {metrics[f'precision@{k}']:.1%} ({metrics[f'hits@{k}']} hits)")
            print(f"Recall@{k}: {metrics[f'recall@{k}']:.1%}")
            print()
    
    display_sample_matches(matches_found, limit=5)
    display_sample_misses(matches_found, limit=5)
    
    output_file = 'evaluation/baseline_results.json'
    output = {
        'benchmark_size': len(bc1_benchmark),
        'high_quality_size': len(bc1_high),
        'v6_results_count': len(results),
        'metrics': metrics,
        'parameters': {
            'source': 'lucan.bellum_civile.part.1',
            'target': 'vergil.aeneid',
            'match_type': 'lemma',
            'min_matches': 2,
            'max_distance': 10
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to {output_file}")

if __name__ == '__main__':
    main()
