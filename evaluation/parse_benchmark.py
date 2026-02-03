#!/usr/bin/env python3
"""
Parse Tesserae benchmark files into structured JSON format.
"""

import json
import csv
import os
import re

def parse_bench41(filepath):
    """
    Parse bench41.txt (Lucan BC1 vs Vergil Aeneid benchmark).
    
    Format is TAB-separated:
    BC_BOOK  BC_LINE  BC_TEXT  AEN_BOOK  AEN_LINE  AEN_TEXT  TYPE  AUTH
    
    TYPE appears to be a 1-4 relevance scale.
    """
    parallels = []
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if i == 0 and 'BC_BOOK' in line:
            continue
        
        parts = line.strip().split('\t')
        
        if len(parts) >= 7:
            try:
                def clean(s):
                    return s.strip('"').strip()
                
                bc_book = clean(parts[0])
                bc_line = clean(parts[1])
                bc_text = clean(parts[2])
                aen_book = clean(parts[3])
                aen_line = clean(parts[4])
                aen_text = clean(parts[5])
                rel_type = clean(parts[6]) if len(parts) > 6 else ''
                auth = clean(parts[7]) if len(parts) > 7 else ''
                
                parallel = {
                    'id': i,
                    'source': {
                        'work': 'Lucan, Bellum Civile',
                        'book': int(bc_book) if bc_book.isdigit() else bc_book,
                        'line': int(bc_line) if bc_line.isdigit() else bc_line,
                        'text': bc_text[:200] + '...' if len(bc_text) > 200 else bc_text
                    },
                    'target': {
                        'work': 'Vergil, Aeneid',
                        'book': int(aen_book) if aen_book.isdigit() else aen_book,
                        'line': int(aen_line) if aen_line.isdigit() else aen_line,
                        'text': aen_text[:200] + '...' if len(aen_text) > 200 else aen_text
                    },
                    'relevance_type': int(rel_type) if rel_type.isdigit() else rel_type,
                    'authority': int(auth) if auth.isdigit() else auth
                }
                parallels.append(parallel)
            except (ValueError, IndexError) as e:
                print(f"Skipping malformed line {i}: {e}")
                continue
    
    return parallels


def parse_vf_dataset(filepath):
    """
    Parse Valerius Flaccus intertext dataset (TAB format).
    """
    parallels = []
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f, delimiter='\t')
        headers = next(reader, None)
        
        for i, row in enumerate(reader):
            if len(row) >= 15:
                try:
                    parallel = {
                        'id': i + 1,
                        'source': {
                            'work': 'Valerius Flaccus, Argonautica 1',
                            'line_start': int(row[0]) if row[0].isdigit() else row[0],
                            'line_end': int(row[1]) if row[1].isdigit() else row[1],
                            'lemma': row[2]
                        },
                        'target': {
                            'author': row[3],
                            'work': row[4],
                            'book': row[5],
                            'line_start': int(row[6]) if row[6].isdigit() else row[6],
                            'line_end': int(row[7]) if row[7].isdigit() else row[7]
                        },
                        'commentary_refs': {
                            'kleywegt': row[8] if len(row) > 8 else '',
                            'zissos': row[9] if len(row) > 9 else '',
                            'spaltenstein': row[10] if len(row) > 10 else ''
                        },
                        'intertext_phrase': row[11] if len(row) > 11 else '',
                        'query_phrase': row[12] if len(row) > 12 else '',
                        'result_phrase': row[13] if len(row) > 13 else '',
                        'order_free': row[14].lower() == 'y' if len(row) > 14 else False,
                        'interval': int(row[15]) if len(row) > 15 and row[15].isdigit() else None,
                        'edit_distance': int(row[16]) if len(row) > 16 and row[16].isdigit() else None
                    }
                    parallels.append(parallel)
                except (ValueError, IndexError) as e:
                    print(f"Skipping malformed row {i}: {e}")
                    continue
    
    return parallels


def format_for_display(parallels, limit=5):
    """Format parallels for human-readable display."""
    output = []
    for p in parallels[:limit]:
        source = p.get('source', {})
        target = p.get('target', {})
        
        if 'text' in source:
            output.append(f"--- Parallel #{p['id']} ---")
            output.append(f"SOURCE: {source['work']} {source['book']}.{source['line']}")
            output.append(f"  Text: {source['text'][:100]}...")
            output.append(f"TARGET: {target['work']} {target['book']}.{target['line']}")
            output.append(f"  Text: {target['text'][:100]}...")
            output.append(f"RELEVANCE: Type {p.get('relevance_type', 'N/A')} | Authority: {p.get('authority', 'N/A')}")
            output.append("")
        else:
            output.append(f"--- Parallel #{p['id']} ---")
            output.append(f"SOURCE: {source['work']} lines {source.get('line_start', '?')}-{source.get('line_end', '?')}")
            output.append(f"  Lemma: {source.get('lemma', 'N/A')}")
            output.append(f"TARGET: {target.get('author', '')} {target.get('work', '')} {target.get('book', '')}.{target.get('line_start', '?')}-{target.get('line_end', '?')}")
            output.append(f"  Phrase: {p.get('intertext_phrase', 'N/A')}")
            output.append(f"ORDER FREE: {p.get('order_free', 'N/A')} | Interval: {p.get('interval', 'N/A')} | Edit Dist: {p.get('edit_distance', 'N/A')}")
            output.append("")
    
    return '\n'.join(output)


if __name__ == '__main__':
    import sys
    
    bench41_path = 'static/downloads/benchmarks/bench41.txt'
    vf_path = 'static/downloads/benchmarks/vf_intertext_dataset_2.0.tab'
    
    print("=" * 60)
    print("PARSING LUCAN-VERGIL BENCHMARK (bench41.txt)")
    print("=" * 60)
    
    if os.path.exists(bench41_path):
        lucan_parallels = parse_bench41(bench41_path)
        print(f"\nTotal parallels parsed: {len(lucan_parallels)}")
        print(f"\nRelevance Type distribution:")
        types = {}
        for p in lucan_parallels:
            t = p.get('relevance_type', 'unknown')
            types[t] = types.get(t, 0) + 1
        for t, count in sorted(types.items()):
            print(f"  Type {t}: {count} parallels")
        
        print("\n" + "-" * 60)
        print("SAMPLE PARALLELS (first 5):")
        print("-" * 60)
        print(format_for_display(lucan_parallels, 5))
        
        with open('evaluation/lucan_vergil_benchmark.json', 'w') as f:
            json.dump(lucan_parallels, f, indent=2)
        print(f"Saved to evaluation/lucan_vergil_benchmark.json")
    else:
        print(f"File not found: {bench41_path}")
    
    print("\n" + "=" * 60)
    print("PARSING VALERIUS FLACCUS DATASET")
    print("=" * 60)
    
    if os.path.exists(vf_path):
        vf_parallels = parse_vf_dataset(vf_path)
        print(f"\nTotal parallels parsed: {len(vf_parallels)}")
        
        targets = {}
        for p in vf_parallels:
            t = p['target'].get('author', 'unknown')
            targets[t] = targets.get(t, 0) + 1
        print(f"\nTarget authors:")
        for t, count in sorted(targets.items(), key=lambda x: -x[1]):
            print(f"  {t}: {count} parallels")
        
        print("\n" + "-" * 60)
        print("SAMPLE PARALLELS (first 5):")
        print("-" * 60)
        print(format_for_display(vf_parallels, 5))
        
        with open('evaluation/vf_benchmark.json', 'w') as f:
            json.dump(vf_parallels, f, indent=2)
        print(f"Saved to evaluation/vf_benchmark.json")
    else:
        print(f"File not found: {vf_path}")
