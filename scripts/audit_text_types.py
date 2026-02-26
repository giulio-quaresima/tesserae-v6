#!/usr/bin/env python3
"""
Audit text type classifications across the entire corpus.

Compares current detect_text_type() classification with a content-based
heuristic (median line length) to find misclassified texts.

Usage:
    cd ~/tesserae-v6-dev && source venv/bin/activate
    python scripts/audit_text_types.py              # full audit
    python scripts/audit_text_types.py --changes    # only show classification changes
    python scripts/audit_text_types.py --grayzone   # only show gray-zone texts (median 70-130 chars)
"""

import os
import sys
import re
import argparse
import statistics

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils import detect_text_type


TEXTS_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'texts')


def compute_median_line_length(filepath):
    """Compute median line length (text only, after stripping <reference> tags)."""
    lengths = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Strip <reference> tags at start of line
                text = re.sub(r'^<[^>]+>\s*', '', line)
                text = text.strip()
                if text:
                    lengths.append(len(text))
    except Exception as e:
        return None

    if not lengths:
        return None
    return statistics.median(lengths)


def content_heuristic(median_len):
    """Classify by median line length. >100 chars = prose, ≤100 = poetry."""
    if median_len is None:
        return 'unknown'
    return 'prose' if median_len > 100 else 'poetry'


def audit_all_texts():
    """Audit all .tess files across all language directories."""
    results = []

    for lang in ['la', 'grc', 'en']:
        lang_dir = os.path.join(TEXTS_ROOT, lang)
        if not os.path.isdir(lang_dir):
            continue

        filenames = sorted(f for f in os.listdir(lang_dir) if f.endswith('.tess'))
        for filename in filenames:
            filepath = os.path.join(lang_dir, filename)

            current_type = detect_text_type(filename, filepath=filepath, language=lang)
            median_len = compute_median_line_length(filepath)
            heuristic_type = content_heuristic(median_len)

            results.append({
                'lang': lang,
                'filename': filename,
                'current': current_type,
                'median_len': median_len,
                'heuristic': heuristic_type,
                'changed': current_type != heuristic_type and heuristic_type != 'unknown',
                'grayzone': median_len is not None and 70 <= median_len <= 130,
            })

    return results


def print_results(results, show_changes=False, show_grayzone=False):
    """Print audit results as a formatted table."""
    if show_changes:
        results = [r for r in results if r['changed']]
        print(f"\n=== CLASSIFICATION CHANGES ({len(results)} texts) ===\n")
    elif show_grayzone:
        results = [r for r in results if r['grayzone']]
        print(f"\n=== GRAY-ZONE TEXTS (median 70-130 chars) ({len(results)} texts) ===\n")
    else:
        print(f"\n=== FULL AUDIT ({len(results)} texts) ===\n")

    # Summary counts
    all_results = results  # for summary when not filtered
    prose_count = sum(1 for r in results if r['current'] == 'prose')
    poetry_count = sum(1 for r in results if r['current'] == 'poetry')
    change_count = sum(1 for r in results if r['changed'])
    gray_count = sum(1 for r in results if r['grayzone'])

    print(f"  Current prose:  {prose_count}")
    print(f"  Current poetry: {poetry_count}")
    print(f"  Changes:        {change_count}")
    print(f"  Gray-zone:      {gray_count}")
    print()

    # Table header
    header = f"{'Lang':<5} {'Filename':<65} {'Current':<10} {'Heuristic':<10} {'Median':<8} {'Flags'}"
    print(header)
    print('-' * len(header))

    for r in results:
        median_str = f"{r['median_len']:.0f}" if r['median_len'] is not None else 'N/A'
        flags = []
        if r['changed']:
            flags.append('CHANGE')
        if r['grayzone']:
            flags.append('GRAY')
        flag_str = ', '.join(flags)
        print(f"{r['lang']:<5} {r['filename']:<65} {r['current']:<10} {r['heuristic']:<10} {median_str:<8} {flag_str}")

    # Summarize changes by direction
    if not show_grayzone:
        prose_to_poetry = [r for r in results if r['changed'] and r['current'] == 'prose' and r['heuristic'] == 'poetry']
        poetry_to_prose = [r for r in results if r['changed'] and r['current'] == 'poetry' and r['heuristic'] == 'prose']
        if prose_to_poetry or poetry_to_prose:
            print(f"\n--- Change Summary ---")
            print(f"  prose → poetry (heuristic): {len(prose_to_poetry)}")
            print(f"  poetry → prose (heuristic): {len(poetry_to_prose)}")


def main():
    parser = argparse.ArgumentParser(description='Audit text type classifications')
    parser.add_argument('--changes', action='store_true', help='Show only texts where classification differs')
    parser.add_argument('--grayzone', action='store_true', help='Show only gray-zone texts (median 70-130 chars)')
    args = parser.parse_args()

    results = audit_all_texts()
    print_results(results, show_changes=args.changes, show_grayzone=args.grayzone)


if __name__ == '__main__':
    main()
