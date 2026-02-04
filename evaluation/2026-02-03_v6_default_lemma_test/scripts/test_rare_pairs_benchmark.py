#!/usr/bin/env python3
"""
Test rare pairs (bigram) and rare unigrams on benchmark parallels.

Uses pre-computed word overlap from benchmark files to analyze rarity
without expensive NLP processing.
"""

import os
import sys
import json
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from backend.bigram_frequency import get_bigram_rarity_score, make_bigram_key
from backend.frequency_cache import load_frequency_cache

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

def get_lemma_frequency(lemma, freq_cache):
    """Get frequency of a lemma from cache"""
    if not freq_cache:
        return 0
    freqs = freq_cache.get('frequencies', {})
    return freqs.get(lemma.lower(), 0)

def load_lucan():
    """Load Lucan-Vergil benchmark with pre-computed overlap"""
    path = os.path.join(DATA_DIR, 'benchmarks', 'lucan_vergil_lexical_benchmark.json')
    with open(path) as f:
        return json.load(f)

def load_achilleid_results():
    """Load Achilleid results with shared lemmas from V6 search"""
    path = os.path.join(DATA_DIR, 'analysis', 'ACHILLEID_FINAL_RESULTS.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

def analyze_lucan(entries, freq_cache):
    """Analyze Lucan-Vergil entries with pre-computed _word_overlap"""
    results = {
        'total_entries': len(entries),
        'type_45_entries': 0,
        'entries_with_2plus_overlap': 0,
        'lemma_rarity': {'has_rare': 0, 'all_common': 0, 'mixed': 0},
        'bigram_rarity': {'has_rare_bigram': 0, 'no_rare_bigram': 0},
        'examples': {'rare_lemmas': [], 'rare_bigrams': [], 'common_only': []},
        'frequency_distribution': Counter()
    }
    
    for entry in entries:
        if entry.get('relevance_type', 0) < 4:
            continue
        results['type_45_entries'] += 1
        
        overlap = entry.get('_word_overlap', [])
        if len(overlap) < 2:
            continue
        
        results['entries_with_2plus_overlap'] += 1
        
        has_rare = False
        has_common = False
        lemma_freqs = []
        
        for word in overlap:
            freq = get_lemma_frequency(word, freq_cache)
            results['frequency_distribution'][freq] += 1
            lemma_freqs.append((word, freq))
            if freq <= 20:
                has_rare = True
            if freq > 100:
                has_common = True
        
        source = entry.get('source', {})
        target = entry.get('target', {})
        source_loc = f"{source.get('work', '')} {source.get('book', '')}.{source.get('line', '')}"
        target_loc = f"{target.get('work', '')} {target.get('book', '')}.{target.get('line', '')}"
        
        if has_rare and not has_common:
            results['lemma_rarity']['has_rare'] += 1
        elif has_common and not has_rare:
            results['lemma_rarity']['all_common'] += 1
            if len(results['examples']['common_only']) < 10:
                results['examples']['common_only'].append({
                    'source': source_loc, 'target': target_loc, 'lemmas': lemma_freqs
                })
        else:
            results['lemma_rarity']['mixed'] += 1
            if has_rare and len(results['examples']['rare_lemmas']) < 10:
                results['examples']['rare_lemmas'].append({
                    'source': source_loc, 'target': target_loc, 'lemmas': lemma_freqs
                })
        
        has_rare_bigram = False
        bigram_scores = []
        for i, w1 in enumerate(overlap):
            for w2 in overlap[i+1:]:
                key = make_bigram_key(w1, w2)
                rarity = get_bigram_rarity_score(key, 'la')
                bigram_scores.append((f"{w1}+{w2}", rarity))
                if rarity >= 0.7:
                    has_rare_bigram = True
        
        if has_rare_bigram:
            results['bigram_rarity']['has_rare_bigram'] += 1
            if len(results['examples']['rare_bigrams']) < 10:
                rare = [(p, r) for p, r in bigram_scores if r >= 0.7]
                results['examples']['rare_bigrams'].append({
                    'source': source_loc, 'target': target_loc, 'pairs': rare
                })
        else:
            results['bigram_rarity']['no_rare_bigram'] += 1
    
    return results

def analyze_achilleid(data, freq_cache):
    """Analyze Achilleid V6 search results"""
    results = {
        'total_found': 0,
        'entries_with_2plus_lemmas': 0,
        'lemma_rarity': {'has_rare': 0, 'all_common': 0, 'mixed': 0},
        'bigram_rarity': {'has_rare_bigram': 0, 'no_rare_bigram': 0},
        'examples': {'rare_lemmas': [], 'rare_bigrams': [], 'common_only': []},
        'frequency_distribution': Counter()
    }
    
    if not data:
        return results
    
    found = data.get('found_parallels', [])
    results['total_found'] = len(found)
    
    for entry in found:
        match_data = entry.get('match_data', {})
        shared = match_data.get('matched_lemmas', [])
        
        if len(shared) < 2:
            continue
        
        results['entries_with_2plus_lemmas'] += 1
        
        has_rare = False
        has_common = False
        lemma_freqs = []
        
        for lemma in shared:
            freq = get_lemma_frequency(lemma, freq_cache)
            results['frequency_distribution'][freq] += 1
            lemma_freqs.append((lemma, freq))
            if freq <= 20:
                has_rare = True
            if freq > 100:
                has_common = True
        
        source_loc = entry.get('source_loc', '')
        target_loc = entry.get('target_loc', '')
        
        if has_rare and not has_common:
            results['lemma_rarity']['has_rare'] += 1
        elif has_common and not has_rare:
            results['lemma_rarity']['all_common'] += 1
            if len(results['examples']['common_only']) < 10:
                results['examples']['common_only'].append({
                    'source': source_loc, 'target': target_loc, 'lemmas': lemma_freqs
                })
        else:
            results['lemma_rarity']['mixed'] += 1
            if has_rare and len(results['examples']['rare_lemmas']) < 10:
                results['examples']['rare_lemmas'].append({
                    'source': source_loc, 'target': target_loc, 'lemmas': lemma_freqs
                })
        
        has_rare_bigram = False
        bigram_scores = []
        for i, l1 in enumerate(shared):
            for l2 in shared[i+1:]:
                key = make_bigram_key(l1, l2)
                rarity = get_bigram_rarity_score(key, 'la')
                bigram_scores.append((f"{l1}+{l2}", rarity))
                if rarity >= 0.7:
                    has_rare_bigram = True
        
        if has_rare_bigram:
            results['bigram_rarity']['has_rare_bigram'] += 1
            if len(results['examples']['rare_bigrams']) < 10:
                rare = [(p, r) for p, r in bigram_scores if r >= 0.7]
                results['examples']['rare_bigrams'].append({
                    'source': source_loc, 'target': target_loc, 'pairs': rare
                })
        else:
            results['bigram_rarity']['no_rare_bigram'] += 1
    
    return results

def print_results(name, results, key='entries_with_2plus_overlap'):
    """Print analysis results"""
    n = results.get(key, results.get('entries_with_2plus_lemmas', 0))
    if n == 0:
        print(f"  No entries with 2+ shared lemmas")
        return
    
    print(f"  Entries with 2+ shared lemmas: {n}")
    
    lr = results['lemma_rarity']
    total_classified = lr['has_rare'] + lr['all_common'] + lr['mixed']
    
    print(f"\n  Lemma rarity (freq ≤20 = rare, >100 = common):")
    print(f"    Has rare lemma: {lr['has_rare'] + lr['mixed']} ({100*(lr['has_rare']+lr['mixed'])/n:.1f}%)")
    print(f"    All rare: {lr['has_rare']} ({100*lr['has_rare']/n:.1f}%)")
    print(f"    All common (no rare): {lr['all_common']} ({100*lr['all_common']/n:.1f}%)")
    
    br = results['bigram_rarity']
    total_bigram = br['has_rare_bigram'] + br['no_rare_bigram']
    if total_bigram > 0:
        print(f"\n  Bigram rarity (rarity ≥0.7 = rare pair):")
        print(f"    Has rare bigram: {br['has_rare_bigram']} ({100*br['has_rare_bigram']/total_bigram:.1f}%)")
        print(f"    No rare bigram: {br['no_rare_bigram']} ({100*br['no_rare_bigram']/total_bigram:.1f}%)")

def main():
    print("=" * 70)
    print("RARE VOCABULARY BENCHMARK ANALYSIS")
    print("=" * 70)
    
    freq_cache = load_frequency_cache('la')
    if freq_cache:
        print(f"Loaded Latin frequency cache with {len(freq_cache.get('frequencies', {}))} lemmas")
    else:
        print("WARNING: No frequency cache available")
    
    all_results = {}
    
    print("\n" + "-" * 50)
    print("LUCAN-VERGIL (type 4-5 entries)")
    print("-" * 50)
    lucan = load_lucan()
    luc_results = analyze_lucan(lucan, freq_cache)
    all_results['lucan_vergil'] = luc_results
    
    print(f"Total entries: {luc_results['total_entries']}")
    print(f"Type 4-5 entries: {luc_results['type_45_entries']}")
    print_results('Lucan', luc_results, 'entries_with_2plus_overlap')
    
    print("\n" + "-" * 50)
    print("ACHILLEID (V6 found parallels)")
    print("-" * 50)
    achilleid = load_achilleid_results()
    if achilleid:
        ach_results = analyze_achilleid(achilleid, freq_cache)
        all_results['achilleid'] = ach_results
        
        print(f"V6 found parallels: {ach_results['total_found']}")
        print_results('Achilleid', ach_results, 'entries_with_2plus_lemmas')
    else:
        print("Could not load Achilleid results")
    
    print("\n" + "=" * 70)
    print("EXAMPLES")
    print("=" * 70)
    
    for name, res in all_results.items():
        ex = res['examples']
        
        if ex['rare_lemmas']:
            print(f"\n{name.upper()} - Entries with RARE lemmas:")
            for e in ex['rare_lemmas'][:3]:
                lemmas = ', '.join([f"{l}(freq={f})" for l, f in e['lemmas']])
                print(f"  {e['source'][:35]} → {e['target'][:35]}")
                print(f"    {lemmas}")
        
        if ex['rare_bigrams']:
            print(f"\n{name.upper()} - Entries with RARE PAIRS:")
            for e in ex['rare_bigrams'][:3]:
                pairs = ', '.join([f"{p}({r:.2f})" for p, r in e['pairs'][:3]])
                print(f"  {e['source'][:35]} → {e['target'][:35]}")
                print(f"    {pairs}")
        
        if ex['common_only']:
            print(f"\n{name.upper()} - Entries with ONLY COMMON vocabulary:")
            for e in ex['common_only'][:3]:
                lemmas = ', '.join([f"{l}(freq={f})" for l, f in e['lemmas']])
                print(f"  {e['source'][:35]} → {e['target'][:35]}")
                print(f"    {lemmas}")
    
    output_path = os.path.join(DATA_DIR, 'analysis', 'rare_vocabulary_analysis.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    serializable = {}
    for name, res in all_results.items():
        freq_dist = dict(sorted(res['frequency_distribution'].items()))
        serializable[name] = {
            'summary': {
                'entries_analyzed': res.get('entries_with_2plus_overlap', res.get('entries_with_2plus_lemmas', 0)),
                'has_rare_lemma_pct': 0,
                'has_rare_bigram_pct': 0
            },
            'lemma_rarity': res['lemma_rarity'],
            'bigram_rarity': res['bigram_rarity'],
            'frequency_distribution_sample': dict(list(freq_dist.items())[:30]),
            'examples': res['examples']
        }
        
        n = serializable[name]['summary']['entries_analyzed']
        if n > 0:
            lr = res['lemma_rarity']
            br = res['bigram_rarity']
            serializable[name]['summary']['has_rare_lemma_pct'] = round(100 * (lr['has_rare'] + lr['mixed']) / n, 1)
            total_br = br['has_rare_bigram'] + br['no_rare_bigram']
            if total_br > 0:
                serializable[name]['summary']['has_rare_bigram_pct'] = round(100 * br['has_rare_bigram'] / total_br, 1)
    
    with open(output_path, 'w') as f:
        json.dump(serializable, f, indent=2)
    
    print(f"\n\nResults saved to: {output_path}")
    
    print("\n" + "=" * 70)
    print("SUMMARY: RARE VOCABULARY IN BENCHMARK PARALLELS")
    print("=" * 70)
    
    for name, res in serializable.items():
        s = res['summary']
        print(f"\n{name.upper()}:")
        print(f"  Parallels with 2+ lemmas: {s['entries_analyzed']}")
        print(f"  Has rare lemma (freq ≤20): {s['has_rare_lemma_pct']}%")
        print(f"  Has rare bigram (rarity ≥0.7): {s['has_rare_bigram_pct']}%")

if __name__ == '__main__':
    main()
