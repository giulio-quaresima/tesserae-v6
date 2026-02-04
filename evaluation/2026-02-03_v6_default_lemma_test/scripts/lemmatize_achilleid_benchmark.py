#!/usr/bin/env python3
"""
Lemmatize Achilleid Benchmark Entries

This script:
1. Loads all Achilleid benchmark entries
2. Fetches actual text lines from the corpus
3. Lemmatizes both source (Achilleid) and target lines
4. Counts shared lemmas for each entry
5. Classifies entries by lemma overlap (0, 1, 2+)
6. Calculates V6 recall on truly lexical subset

Author: Tesserae V6 Evaluation
Date: February 4, 2026
"""

import json
import os
import re
import sys

sys.path.insert(0, '/home/runner/workspace')

BASE_DIR = '/home/runner/workspace/evaluation/2026-02-03_v6_default_lemma_test'
BENCHMARK_FILE = os.path.join(BASE_DIR, 'data/benchmarks/achilleid_benchmark_classified.json')
CORPUS_DIR = '/home/runner/workspace/texts/la'
OUTPUT_FILE = os.path.join(BASE_DIR, 'data/analysis/achilleid_lemmatized.json')


def load_text_lines(filepath):
    """Load all lines from a .tess file"""
    lines = {}
    if not os.path.exists(filepath):
        return lines
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith('<'):
                continue
            
            match = re.match(r'<[^>]+\s+(\d+)\.(\d+)>(.+)', line)
            if match:
                book = int(match.group(1))
                line_num = int(match.group(2))
                text = match.group(3).strip()
                key = f"{book}_{line_num}"
                lines[key] = text
    
    return lines


def simple_tokenize(text):
    """Simple Latin tokenization"""
    text = text.lower()
    text = re.sub(r'[^a-z\s]', '', text)
    tokens = text.split()
    return [t for t in tokens if len(t) > 1]


# Load Latin lemma mappings
print("Loading Latin lemma mappings...")
LATIN_LEMMA_TABLE = {}

lemma_file = '/home/runner/workspace/data/lemma_tables/latin_lemmas.json'
if os.path.exists(lemma_file):
    with open(lemma_file, 'r', encoding='utf-8') as f:
        LATIN_LEMMA_TABLE = json.load(f)
    print(f"Loaded {len(LATIN_LEMMA_TABLE)} Latin lemma mappings")
else:
    print("Warning: No Latin lemma table found, using identity mapping")


def normalize_latin(word):
    """Normalize Latin spelling: v→u, j→i"""
    return word.lower().replace('v', 'u').replace('j', 'i')


def lemmatize_word(word):
    """Lemmatize a single Latin word"""
    word = word.lower()
    
    # Handle -que suffix
    base = word
    if word.endswith('que') and len(word) > 3:
        base = word[:-3]
    
    # Try original
    if base in LATIN_LEMMA_TABLE:
        return normalize_latin(LATIN_LEMMA_TABLE[base])
    
    # Try normalized (v→u)
    norm = normalize_latin(base)
    if norm in LATIN_LEMMA_TABLE:
        return normalize_latin(LATIN_LEMMA_TABLE[norm])
    
    # Return normalized form if not found
    return norm


def lemmatize_line(text):
    """Lemmatize all words in a line, return set of lemmas"""
    tokens = simple_tokenize(text)
    lemmas = set()
    for token in tokens:
        lemma = lemmatize_word(token)
        lemmas.add(lemma)
        if 'que' in token:
            base = token.replace('que', '')
            if base:
                lemmas.add(lemmatize_word(base))
    return lemmas


def get_shared_lemmas(lemmas1, lemmas2):
    """Return shared lemmas between two sets"""
    return lemmas1 & lemmas2


def main():
    print("=" * 70)
    print("ACHILLEID BENCHMARK LEMMATIZATION")
    print("=" * 70)
    print()
    
    with open(BENCHMARK_FILE, 'r') as f:
        benchmark = json.load(f)
    
    entries = benchmark['entries']
    print(f"Total benchmark entries: {len(entries)}")
    
    achilleid_path = os.path.join(CORPUS_DIR, 'statius.achilleid.tess')
    achilleid_lines = load_text_lines(achilleid_path)
    print(f"Loaded {len(achilleid_lines)} Achilleid lines")
    
    target_files = set()
    for entry in entries:
        target_work = entry.get('source_work', '')
        if target_work:
            filename = target_work.replace('.', '.') + '.tess'
            target_files.add(filename)
    
    print(f"\nTarget works: {len(target_files)}")
    
    # Fix typos in benchmark data
    WORK_CORRECTIONS = {
        'statius.thebiad': 'statius.thebaid',
    }
    
    target_texts = {}
    for work_key in target_files:
        work_key = work_key.replace('.tess', '')
        corrected_key = WORK_CORRECTIONS.get(work_key, work_key)
        target_texts[work_key] = {}
        
        base_file = os.path.join(CORPUS_DIR, corrected_key + '.tess')
        if os.path.exists(base_file):
            target_texts[work_key] = load_text_lines(base_file)
            print(f"  Loaded {len(target_texts[work_key])} lines from {corrected_key}.tess")
        
        for i in range(1, 20):
            part_file = os.path.join(CORPUS_DIR, f"{corrected_key}.part.{i}.tess")
            if os.path.exists(part_file):
                part_lines = load_text_lines(part_file)
                target_texts[work_key].update(part_lines)
                print(f"    + {len(part_lines)} lines from part {i}")
        
        if not target_texts[work_key]:
            print(f"  Warning: No lines found for {work_key} (tried {corrected_key})")
    
    print("\n" + "-" * 70)
    print("Lemmatizing benchmark entries...")
    print("-" * 70)
    
    results = []
    lemma_counts = {0: 0, 1: 0, '2+': 0}
    found_by_lemma_count = {0: 0, 1: 0, '2+': 0}
    total_by_lemma_count = {0: 0, 1: 0, '2+': 0}
    
    for entry in entries:
        if entry.get('assigned_type', 0) < 4:
            continue
        
        ach_line_key = entry.get('target_line', '').replace('.', '_')
        target_work = entry.get('source_work', '')
        target_line_key = entry.get('source_line', '').replace('.', '_')
        
        ach_text = achilleid_lines.get(ach_line_key, '')
        target_text_content = ''
        
        if target_work in target_texts:
            target_text_content = target_texts[target_work].get(target_line_key, '')
        
        if not ach_text or not target_text_content:
            entry['ach_lemmas'] = []
            entry['target_lemmas'] = []
            entry['shared_lemmas'] = []
            entry['shared_count'] = 0
            entry['lemma_class'] = 'unknown'
            results.append(entry)
            continue
        
        ach_lemmas = lemmatize_line(ach_text)
        target_lemmas = lemmatize_line(target_text_content)
        shared = get_shared_lemmas(ach_lemmas, target_lemmas)
        
        entry['ach_text'] = ach_text
        entry['target_text_full'] = target_text_content
        entry['ach_lemmas'] = list(ach_lemmas)
        entry['target_lemmas'] = list(target_lemmas)
        entry['shared_lemmas'] = list(shared)
        entry['shared_count'] = len(shared)
        
        if len(shared) >= 2:
            entry['lemma_class'] = '2+'
            lemma_counts['2+'] += 1
        elif len(shared) == 1:
            entry['lemma_class'] = '1'
            lemma_counts[1] += 1
        else:
            entry['lemma_class'] = '0'
            lemma_counts[0] += 1
        
        results.append(entry)
    
    print("\n" + "=" * 70)
    print("LEMMA OVERLAP CLASSIFICATION")
    print("=" * 70)
    print(f"\nType 4-5 entries analyzed: {len(results)}")
    print()
    for lc, count in sorted(lemma_counts.items(), key=lambda x: str(x[0])):
        pct = round(count / len(results) * 100, 1)
        print(f"  {lc} shared lemmas: {count} ({pct}%)")
    
    with open('/home/runner/workspace/evaluation/2026-02-03_v6_default_lemma_test/data/analysis/achilleid_recall_results.json') as f:
        recall_results = json.load(f)
    
    found_ids = set()
    for entry in recall_results.get('found_entries', []):
        found_ids.add(entry.get('id'))
    
    for entry in results:
        entry['v6_found'] = entry.get('id') in found_ids
        
        lc = entry.get('lemma_class', 'unknown')
        if lc == '2+':
            total_by_lemma_count['2+'] += 1
            if entry['v6_found']:
                found_by_lemma_count['2+'] += 1
        elif lc == '1':
            total_by_lemma_count[1] += 1
            if entry['v6_found']:
                found_by_lemma_count[1] += 1
        elif lc == '0':
            total_by_lemma_count[0] += 1
            if entry['v6_found']:
                found_by_lemma_count[0] += 1
    
    print("\n" + "=" * 70)
    print("V6 RECALL BY LEMMA OVERLAP CLASS")
    print("=" * 70)
    print()
    
    for lc in ['2+', 1, 0]:
        total = total_by_lemma_count.get(lc, 0)
        found = found_by_lemma_count.get(lc, 0)
        if total > 0:
            recall = round(found / total * 100, 1)
            print(f"  {lc} shared lemmas: {found}/{total} ({recall}%)")
        else:
            print(f"  {lc} shared lemmas: 0/0 (N/A)")
    
    truly_lexical = lemma_counts.get('2+', 0)
    truly_lexical_found = found_by_lemma_count.get('2+', 0)
    if truly_lexical > 0:
        lexical_recall = round(truly_lexical_found / truly_lexical * 100, 1)
        print(f"\n  ** TRULY LEXICAL RECALL (2+ shared lemmas): {truly_lexical_found}/{truly_lexical} ({lexical_recall}%) **")
    
    print("\n" + "-" * 70)
    print("SAMPLE ENTRIES BY CLASS")
    print("-" * 70)
    
    for lc in ['2+', 1, 0]:
        class_entries = [e for e in results if e.get('lemma_class') == str(lc) or (lc == '2+' and e.get('lemma_class') == '2+')]
        print(f"\n=== {lc} shared lemmas (sample of 3) ===")
        for entry in class_entries[:3]:
            print(f"\n  Achilleid {entry.get('target_line')} → {entry.get('source_work')} {entry.get('source_line')}")
            print(f"    Achilleid: {entry.get('ach_text', 'N/A')[:80]}")
            print(f"    Target: {entry.get('target_text_full', 'N/A')[:80]}")
            print(f"    Shared lemmas: {entry.get('shared_lemmas', [])}")
            print(f"    V6 found: {entry.get('v6_found', False)}")
    
    output = {
        'summary': {
            'total_analyzed': len(results),
            'by_lemma_class': lemma_counts,
            'recall_by_class': {
                '2+': {'found': found_by_lemma_count.get('2+', 0), 'total': total_by_lemma_count.get('2+', 0)},
                '1': {'found': found_by_lemma_count.get(1, 0), 'total': total_by_lemma_count.get(1, 0)},
                '0': {'found': found_by_lemma_count.get(0, 0), 'total': total_by_lemma_count.get(0, 0)},
            }
        },
        'entries': results
    }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n\nResults saved to: {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
