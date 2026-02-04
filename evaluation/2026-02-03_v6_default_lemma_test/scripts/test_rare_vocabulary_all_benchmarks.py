#!/usr/bin/env python3
"""
Test rare pairs (bigram) and rare unigrams across ALL benchmarks.

Analyzes Lucan-Vergil, Valerius Flaccus, and Achilleid benchmarks
for rare vocabulary that could improve precision.
"""

import os
import sys
import json
import re
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

def extract_words(text):
    """Extract words from text, normalizing Latin"""
    if not text:
        return []
    text = text.lower()
    text = re.sub(r'[^a-z\s]', ' ', text)
    words = [w for w in text.split() if len(w) > 2]
    return words

def analyze_entries(entries, freq_cache, get_shared_fn):
    """Generic analysis function for any benchmark format"""
    results = {
        'total_entries': len(entries),
        'high_quality': 0,
        'entries_with_2plus': 0,
        'lemma_rarity': {'has_rare': 0, 'all_common': 0, 'mixed': 0},
        'bigram_rarity': {'has_rare_bigram': 0, 'no_rare_bigram': 0},
        'examples': {'rare_lemmas': [], 'rare_bigrams': [], 'common_only': []},
        'frequency_distribution': Counter()
    }
    
    for entry in entries:
        shared, source_loc, target_loc, is_high_quality = get_shared_fn(entry)
        
        if not is_high_quality:
            continue
        results['high_quality'] += 1
        
        if len(shared) < 2:
            continue
        
        results['entries_with_2plus'] += 1
        
        has_rare = False
        has_common = False
        lemma_freqs = []
        
        for word in shared:
            freq = get_lemma_frequency(word, freq_cache)
            results['frequency_distribution'][freq] += 1
            lemma_freqs.append((word, freq))
            if freq <= 20:
                has_rare = True
            if freq > 100:
                has_common = True
        
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
        for i, w1 in enumerate(shared):
            for w2 in shared[i+1:]:
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

def load_and_analyze_lucan(freq_cache):
    """Analyze Lucan-Vergil benchmark"""
    path = os.path.join(DATA_DIR, 'benchmarks', 'lucan_vergil_lexical_benchmark.json')
    with open(path) as f:
        entries = json.load(f)
    
    def get_shared(entry):
        overlap = entry.get('_word_overlap', [])
        source = entry.get('source', {})
        target = entry.get('target', {})
        source_loc = f"{source.get('work', '')} {source.get('book', '')}.{source.get('line', '')}"
        target_loc = f"{target.get('work', '')} {target.get('book', '')}.{target.get('line', '')}"
        is_hq = entry.get('relevance_type', 0) >= 4
        return overlap, source_loc, target_loc, is_hq
    
    return analyze_entries(entries, freq_cache, get_shared)

def load_and_analyze_vf(freq_cache):
    """Analyze Valerius Flaccus benchmark"""
    path = os.path.join(DATA_DIR, 'benchmarks', 'vf_benchmark_aligned.json')
    with open(path) as f:
        entries = json.load(f)
    
    def get_shared(entry):
        query = extract_words(entry.get('query_phrase', ''))
        result = extract_words(entry.get('result_phrase', ''))
        shared = list(set(query) & set(result))
        
        source = entry.get('source', {})
        target = entry.get('target', {})
        source_loc = f"VF Arg. {source.get('line_start', '')}"
        target_loc = f"{target.get('author', '')} {target.get('work', '')} {target.get('book', '')}.{target.get('line_start', '')}"
        
        return shared, source_loc, target_loc, True
    
    return analyze_entries(entries, freq_cache, get_shared)

def load_and_analyze_achilleid(freq_cache):
    """Analyze Achilleid benchmark"""
    path = os.path.join(DATA_DIR, 'benchmarks', 'achilleid_benchmark_classified.json')
    with open(path) as f:
        data = json.load(f)
    entries = data.get('entries', [])
    
    def get_shared(entry):
        note = extract_words(entry.get('note', ''))
        target = extract_words(entry.get('target_text', ''))
        
        shared = list(set(note) & set(target)) if note and target else note[:5]
        
        source_loc = f"{entry.get('source_work', '')} {entry.get('source_line', '')}"
        target_loc = f"{entry.get('target_work', '')} {entry.get('target_line', '')}"
        is_hq = entry.get('assigned_type', 0) >= 4
        
        return shared, source_loc, target_loc, is_hq
    
    return analyze_entries(entries, freq_cache, get_shared)

def print_results(name, results):
    """Print analysis results"""
    print(f"\n{'='*60}")
    print(f"{name.upper()}")
    print(f"{'='*60}")
    
    print(f"Total entries: {results['total_entries']}")
    print(f"High-quality (type 4-5): {results['high_quality']}")
    print(f"With 2+ shared words: {results['entries_with_2plus']}")
    
    n = results['entries_with_2plus']
    if n == 0:
        print("  No entries with 2+ shared words to analyze")
        return
    
    lr = results['lemma_rarity']
    has_rare_total = lr['has_rare'] + lr['mixed']
    
    print(f"\nLemma rarity (freq ≤20 = rare, >100 = common):")
    print(f"  Has rare lemma: {has_rare_total} ({100*has_rare_total/n:.1f}%)")
    print(f"    - All rare: {lr['has_rare']} ({100*lr['has_rare']/n:.1f}%)")
    print(f"    - Mixed: {lr['mixed']} ({100*lr['mixed']/n:.1f}%)")
    print(f"  All common (no rare): {lr['all_common']} ({100*lr['all_common']/n:.1f}%)")
    
    br = results['bigram_rarity']
    total_br = br['has_rare_bigram'] + br['no_rare_bigram']
    if total_br > 0:
        print(f"\nBigram rarity (rarity ≥0.7 = rare pair):")
        print(f"  Has rare bigram: {br['has_rare_bigram']} ({100*br['has_rare_bigram']/total_br:.1f}%)")
        print(f"  No rare bigram: {br['no_rare_bigram']} ({100*br['no_rare_bigram']/total_br:.1f}%)")

def main():
    print("=" * 70)
    print("RARE VOCABULARY ANALYSIS - ALL BENCHMARKS")
    print("=" * 70)
    
    freq_cache = load_frequency_cache('la')
    if freq_cache:
        print(f"Loaded Latin frequency cache with {len(freq_cache.get('frequencies', {}))} lemmas")
    else:
        print("WARNING: No frequency cache available")
    
    all_results = {}
    
    print("\nAnalyzing Lucan-Vergil...")
    all_results['lucan_vergil'] = load_and_analyze_lucan(freq_cache)
    print_results('Lucan-Vergil', all_results['lucan_vergil'])
    
    print("\nAnalyzing Valerius Flaccus...")
    all_results['valerius_flaccus'] = load_and_analyze_vf(freq_cache)
    print_results('Valerius Flaccus', all_results['valerius_flaccus'])
    
    print("\nAnalyzing Achilleid...")
    all_results['achilleid'] = load_and_analyze_achilleid(freq_cache)
    print_results('Achilleid', all_results['achilleid'])
    
    print("\n" + "=" * 70)
    print("SUMMARY TABLE")
    print("=" * 70)
    
    print(f"\n{'Benchmark':<20} {'2+ Words':<10} {'Has Rare Lemma':<18} {'Has Rare Bigram':<18}")
    print("-" * 70)
    
    for name, res in all_results.items():
        n = res['entries_with_2plus']
        if n > 0:
            lr = res['lemma_rarity']
            br = res['bigram_rarity']
            has_rare_lemma = lr['has_rare'] + lr['mixed']
            total_br = br['has_rare_bigram'] + br['no_rare_bigram']
            rare_bigram_pct = 100 * br['has_rare_bigram'] / total_br if total_br > 0 else 0
            print(f"{name:<20} {n:<10} {has_rare_lemma}/{n} ({100*has_rare_lemma/n:.1f}%)     {br['has_rare_bigram']}/{total_br} ({rare_bigram_pct:.1f}%)")
        else:
            print(f"{name:<20} {n:<10} N/A                N/A")
    
    output_path = os.path.join(DATA_DIR, 'analysis', 'rare_vocabulary_all_benchmarks.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    serializable = {}
    for name, res in all_results.items():
        n = res['entries_with_2plus']
        lr = res['lemma_rarity']
        br = res['bigram_rarity']
        
        serializable[name] = {
            'summary': {
                'total_entries': res['total_entries'],
                'high_quality': res['high_quality'],
                'entries_with_2plus': n,
                'has_rare_lemma_count': lr['has_rare'] + lr['mixed'],
                'has_rare_lemma_pct': round(100 * (lr['has_rare'] + lr['mixed']) / n, 1) if n > 0 else 0,
                'has_rare_bigram_count': br['has_rare_bigram'],
                'has_rare_bigram_pct': round(100 * br['has_rare_bigram'] / (br['has_rare_bigram'] + br['no_rare_bigram']), 1) if (br['has_rare_bigram'] + br['no_rare_bigram']) > 0 else 0
            },
            'lemma_rarity': res['lemma_rarity'],
            'bigram_rarity': res['bigram_rarity'],
            'examples': res['examples']
        }
    
    with open(output_path, 'w') as f:
        json.dump(serializable, f, indent=2)
    
    print(f"\n\nResults saved to: {output_path}")
    
    print("\n" + "=" * 70)
    print("KEY FINDINGS")
    print("=" * 70)
    
    for name, res in serializable.items():
        s = res['summary']
        if s['entries_with_2plus'] > 0:
            print(f"\n{name.upper()}:")
            print(f"  {s['has_rare_lemma_pct']}% have rare lemmas (freq ≤20)")
            print(f"  {s['has_rare_bigram_pct']}% have rare bigrams (rarity ≥0.7)")

if __name__ == '__main__':
    main()
