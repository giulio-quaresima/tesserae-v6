#!/usr/bin/env python3
"""
Error Analysis: Why is V6 missing high-quality parallels?

Examines Type 4-5 benchmark parallels that V6 did NOT find to understand
the systematic gaps in recall.
"""

import json
import requests
import os
from collections import Counter

API_BASE = os.environ.get('API_BASE', 'http://localhost:5000')

def load_benchmark():
    with open('evaluation/lucan_vergil_benchmark.json') as f:
        return json.load(f)

def load_v6_results():
    with open('evaluation/full_default_evaluation_results.json') as f:
        return json.load(f)

def get_text_content(text_id):
    """Fetch text content from API."""
    url = f"{API_BASE}/api/texts/{text_id}"
    try:
        resp = requests.get(url, timeout=30)
        if resp.ok:
            return resp.json()
    except:
        pass
    return None

def get_lemmas_for_line(text_id, line_num):
    """Get lemmatized tokens for a specific line."""
    url = f"{API_BASE}/api/texts/{text_id}/lines/{line_num}"
    try:
        resp = requests.get(url, timeout=30)
        if resp.ok:
            data = resp.json()
            return data.get('lemmas', []), data.get('tokens', [])
    except:
        pass
    return [], []

def run_single_search(source_text, target_text, settings):
    """Run a V6 search."""
    url = f"{API_BASE}/api/search"
    payload = {
        'source': source_text,
        'target': target_text,
        'language': 'la',
        'settings': settings
    }
    try:
        resp = requests.post(url, json=payload, timeout=120)
        if resp.ok:
            return resp.json()
    except Exception as e:
        print(f"Search error: {e}")
    return None

def parse_v6_ref(ref_str):
    """Parse reference like 'luc. 1.13' to (book, line)."""
    parts = ref_str.split('.')
    if len(parts) >= 2:
        try:
            return (int(parts[-2]), int(parts[-1]))
        except:
            pass
    return (None, None)

def find_in_v6_results(v6_results, source_line, target_book, target_line, tolerance=2):
    """Check if a benchmark parallel appears in V6 results."""
    for i, result in enumerate(v6_results):
        source_ref = result.get('source', {}).get('ref', '')
        target_ref = result.get('target', {}).get('ref', '')
        
        _, v6_source_line = parse_v6_ref(source_ref)
        v6_target_book, v6_target_line = parse_v6_ref(target_ref)
        
        if v6_source_line is None or v6_target_line is None:
            continue
            
        if (abs(v6_source_line - source_line) <= tolerance and
            v6_target_book == target_book and
            abs(v6_target_line - target_line) <= tolerance):
            return i, result
    
    return None, None

def analyze_missed_parallel(parallel, source_lemmas_cache, target_lemmas_cache):
    """Analyze why a specific parallel was missed."""
    source_line = parallel['source']['line']
    target_book = parallel['target']['book']
    target_line = parallel['target']['line']
    
    source_key = f"bc1_{source_line}"
    target_key = f"aen{target_book}_{target_line}"
    
    source_lemmas = source_lemmas_cache.get(source_key, set())
    target_lemmas = target_lemmas_cache.get(target_key, set())
    
    overlap = source_lemmas & target_lemmas
    
    analysis = {
        'source_line': source_line,
        'target_book': target_book,
        'target_line': target_line,
        'relevance_type': parallel.get('relevance_type'),
        'source_text': parallel['source'].get('text', '')[:80],
        'target_text': parallel['target'].get('text', '')[:80],
        'source_lemmas': list(source_lemmas)[:20],
        'target_lemmas': list(target_lemmas)[:20],
        'lemma_overlap': list(overlap),
        'overlap_count': len(overlap),
    }
    
    if len(overlap) < 2:
        analysis['failure_reason'] = 'insufficient_lemma_overlap'
    else:
        analysis['failure_reason'] = 'unknown_needs_investigation'
    
    return analysis

def main():
    print("=" * 70)
    print("ERROR ANALYSIS: Why is V6 missing high-quality parallels?")
    print("=" * 70)
    
    benchmark = load_benchmark()
    bc1_benchmark = [p for p in benchmark if p['source'].get('book') == 1]
    high_quality = [p for p in bc1_benchmark if p.get('relevance_type', 0) >= 4]
    
    print(f"\nHigh-quality parallels (Type 4-5): {len(high_quality)}")
    
    print("\nRunning V6 search to identify found vs missed...")
    
    all_v6_results = []
    for aen_book in range(1, 13):
        target = f'vergil.aeneid.part.{aen_book}.tess'
        result = run_single_search(
            'lucan.bellum_civile.part.1.tess',
            target,
            {
                'match_type': 'lemma',
                'min_matches': 2,
                'max_distance': 20,
                'max_results': 500,
                'stoplist_size': 0
            }
        )
        if result and 'results' in result:
            for r in result['results']:
                r['_aen_book'] = aen_book
            all_v6_results.extend(result['results'])
    
    all_v6_results.sort(key=lambda x: x.get('overall_score', 0), reverse=True)
    print(f"Total V6 results: {len(all_v6_results)}")
    
    found = []
    missed = []
    
    for parallel in high_quality:
        source_line = parallel['source']['line']
        target_book = parallel['target']['book']
        target_line = parallel['target']['line']
        
        rank, match = find_in_v6_results(all_v6_results, source_line, target_book, target_line)
        
        if match:
            found.append((parallel, rank, match))
        else:
            missed.append(parallel)
    
    print(f"\nFound: {len(found)} / {len(high_quality)} ({len(found)/len(high_quality)*100:.1f}%)")
    print(f"Missed: {len(missed)} / {len(high_quality)} ({len(missed)/len(high_quality)*100:.1f}%)")
    
    print("\n" + "=" * 70)
    print("ANALYZING MISSED PARALLELS")
    print("=" * 70)
    
    print("\nFetching lemma data for missed parallels...")
    
    source_lemmas_cache = {}
    target_lemmas_cache = {}
    
    for parallel in missed[:50]:
        source_line = parallel['source']['line']
        target_book = parallel['target']['book']
        target_line = parallel['target']['line']
        
        source_key = f"bc1_{source_line}"
        if source_key not in source_lemmas_cache:
            lemmas, _ = get_lemmas_for_line('lucan.bellum_civile.part.1.tess', source_line)
            source_lemmas_cache[source_key] = set(lemmas)
        
        target_key = f"aen{target_book}_{target_line}"
        if target_key not in target_lemmas_cache:
            lemmas, _ = get_lemmas_for_line(f'vergil.aeneid.part.{target_book}.tess', target_line)
            target_lemmas_cache[target_key] = set(lemmas)
    
    failure_reasons = Counter()
    overlap_counts = Counter()
    
    detailed_analyses = []
    
    for parallel in missed[:50]:
        analysis = analyze_missed_parallel(parallel, source_lemmas_cache, target_lemmas_cache)
        detailed_analyses.append(analysis)
        failure_reasons[analysis['failure_reason']] += 1
        overlap_counts[analysis['overlap_count']] += 1
    
    print("\n" + "-" * 70)
    print("FAILURE REASON BREAKDOWN (first 50 missed)")
    print("-" * 70)
    for reason, count in failure_reasons.most_common():
        print(f"  {reason}: {count}")
    
    print("\n" + "-" * 70)
    print("LEMMA OVERLAP DISTRIBUTION (first 50 missed)")
    print("-" * 70)
    for overlap, count in sorted(overlap_counts.items()):
        print(f"  {overlap} overlapping lemmas: {count} parallels")
    
    print("\n" + "-" * 70)
    print("SAMPLE MISSED PARALLELS WITH DETAILS")
    print("-" * 70)
    
    for i, analysis in enumerate(detailed_analyses[:15]):
        print(f"\n--- Missed #{i+1} (Type {analysis['relevance_type']}) ---")
        print(f"BC1.{analysis['source_line']} → Aen.{analysis['target_book']}.{analysis['target_line']}")
        print(f"Source: {analysis['source_text']}...")
        print(f"Target: {analysis['target_text']}...")
        print(f"Source lemmas: {analysis['source_lemmas'][:10]}")
        print(f"Target lemmas: {analysis['target_lemmas'][:10]}")
        print(f"OVERLAP: {analysis['lemma_overlap']} ({analysis['overlap_count']} lemmas)")
        print(f"Failure: {analysis['failure_reason']}")
    
    output = {
        'total_high_quality': len(high_quality),
        'found': len(found),
        'missed': len(missed),
        'failure_reasons': dict(failure_reasons),
        'overlap_distribution': dict(overlap_counts),
        'detailed_analyses': detailed_analyses
    }
    
    with open('evaluation/error_analysis_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n\nResults saved to evaluation/error_analysis_results.json")
    
    print("\n" + "=" * 70)
    print("PRELIMINARY CONCLUSIONS")
    print("=" * 70)
    
    no_overlap = overlap_counts.get(0, 0) + overlap_counts.get(1, 0)
    has_overlap = sum(c for o, c in overlap_counts.items() if o >= 2)
    
    print(f"""
Analyzed {len(detailed_analyses)} missed Type 4-5 parallels:

1. LEMMA OVERLAP ISSUE: {no_overlap} parallels ({no_overlap/len(detailed_analyses)*100:.0f}%)
   - These have 0 or 1 overlapping lemmas
   - V6 can't find them with min_matches=2
   - Possible causes: lemmatization differences, text variants, phrase-level allusions

2. OTHER ISSUES: {has_overlap} parallels ({has_overlap/len(detailed_analyses)*100:.0f}%)
   - These HAVE 2+ overlapping lemmas but V6 still missed them
   - Possible causes: max_distance exceeded, line boundary issues
   
Next steps:
- For (1): Examine if these are genuine word-level parallels or phrase/thematic
- For (2): Check if increasing max_distance or relaxing constraints helps
""")

if __name__ == '__main__':
    main()
