#!/usr/bin/env python3
"""
Re-segment jerome.epistulae.tess into sentence-length units (~15-20 words per line).

The original file has 4,679 lines averaging ~62 words/line (paragraph-level chunks).
This script splits them into sentence-level units targeting 10-25 words per segment.

Reference scheme:
  Original: <jer. ep. X.Y.Z>
  Split:    <jer. ep. X.Y.Z.1>, <jer. ep. X.Y.Z.2>, etc.
  If a line doesn't need splitting (already <=25 words), keep original reference.

Splitting strategy:
  1. Split on sentence-ending punctuation: . ? !
     - But NOT after common abbreviations (single letters, etc.)
  2. If a resulting segment is still >30 words, split at clause boundaries: ; :
  3. If still >30 words, split at commas (picking the comma closest to the midpoint)
  4. Never split below 5 words (merge short fragments with neighbors)
"""

import re
import sys
import os

INPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'texts', 'la', 'jerome.epistulae.tess')
OUTPUT_FILE = INPUT_FILE  # Overwrite (backup should already exist)

# Target word counts
TARGET_MIN = 8
TARGET_MAX = 25
HARD_MAX = 30  # Trigger secondary splitting above this
MERGE_MIN = 5  # Merge fragments shorter than this


def split_on_sentence_punctuation(text):
    """Split text on sentence-ending punctuation (. ? !), respecting abbreviations."""
    # Split on . ? ! followed by a space and then a word character (or quote/paren)
    # This avoids splitting on abbreviations like "e.g." or single-letter abbrevs
    # Latin abbreviation patterns: single uppercase letter + period (rare in this text)

    # Strategy: split on punctuation followed by space, but handle edge cases
    segments = []
    current = []
    words = text.split()

    for i, word in enumerate(words):
        current.append(word)
        # Check if this word ends with sentence punctuation
        if re.search(r'[.?!][)\'"]*$', word):
            # Don't split after very short abbreviation-like tokens
            # (single char + period, or common Latin abbreviations)
            stripped = re.sub(r'[)\'"]+$', '', word)
            is_abbrev = (len(stripped) <= 2 and stripped.endswith('.') and
                        stripped[:-1].isalpha())

            if not is_abbrev and len(current) >= MERGE_MIN:
                segments.append(' '.join(current))
                current = []

    # Don't forget remaining text
    if current:
        if segments and len(current) < MERGE_MIN:
            # Merge tiny trailing fragment with previous segment
            segments[-1] = segments[-1] + ' ' + ' '.join(current)
        else:
            segments.append(' '.join(current))

    return segments if segments else [text]


def split_on_clause_boundaries(text):
    """Split text on semicolons and colons."""
    segments = []
    current = []
    words = text.split()

    for word in words:
        current.append(word)
        if re.search(r'[;:]$', word) and len(current) >= MERGE_MIN:
            segments.append(' '.join(current))
            current = []

    if current:
        if segments and len(current) < MERGE_MIN:
            segments[-1] = segments[-1] + ' ' + ' '.join(current)
        else:
            segments.append(' '.join(current))

    return segments if segments else [text]


def split_at_comma_near_midpoint(text):
    """Split text at the comma closest to the midpoint."""
    words = text.split()
    n = len(words)
    mid = n // 2

    # Find all comma positions
    comma_positions = []
    for i, word in enumerate(words):
        if word.endswith(',') and i >= MERGE_MIN - 1 and (n - i - 1) >= MERGE_MIN:
            comma_positions.append(i)

    if not comma_positions:
        return [text]  # No good comma to split at

    # Pick comma closest to midpoint
    best = min(comma_positions, key=lambda p: abs(p - mid))

    part1 = ' '.join(words[:best + 1])
    part2 = ' '.join(words[best + 1:])

    return [part1, part2]


def resegment_text(text):
    """Split text into segments targeting TARGET_MIN-TARGET_MAX words each."""
    words = text.split()

    # If already within target, no splitting needed
    if len(words) <= TARGET_MAX:
        return [text]

    # Step 1: Split on sentence punctuation
    segments = split_on_sentence_punctuation(text)

    # Step 2: For segments still too long, split on clause boundaries
    refined = []
    for seg in segments:
        if len(seg.split()) > HARD_MAX:
            refined.extend(split_on_clause_boundaries(seg))
        else:
            refined.append(seg)

    # Step 3: For segments STILL too long, split at commas
    final = []
    for seg in refined:
        if len(seg.split()) > HARD_MAX:
            parts = split_at_comma_near_midpoint(seg)
            # Recursively split if parts are still too long
            for part in parts:
                if len(part.split()) > HARD_MAX:
                    subparts = split_at_comma_near_midpoint(part)
                    final.extend(subparts)
                else:
                    final.append(part)
        else:
            final.append(seg)

    # Step 4: Merge tiny fragments with neighbors
    merged = []
    for seg in final:
        if merged and len(seg.split()) < MERGE_MIN:
            merged[-1] = merged[-1] + ' ' + seg
        elif merged and len(merged[-1].split()) < MERGE_MIN:
            merged[-1] = merged[-1] + ' ' + seg
        else:
            merged.append(seg)

    # Final check: if merging left last segment tiny, merge with previous
    if len(merged) > 1 and len(merged[-1].split()) < MERGE_MIN:
        merged[-2] = merged[-2] + ' ' + merged[-1]
        merged.pop()

    return merged


def process_file(input_path, output_path):
    """Process the .tess file and write re-segmented version."""

    with open(input_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()

    output_lines = []
    total_old_words = 0
    total_new_words = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Parse reference and text
        match = re.match(r'(<[^>]+>)\t(.*)', line)
        if not match:
            # Try space separator
            match = re.match(r'(<[^>]+>)\s+(.*)', line)
        if not match:
            print(f"WARNING: Could not parse line: {line[:80]}", file=sys.stderr)
            output_lines.append(line)
            continue

        ref = match.group(1)
        text = match.group(2).strip()

        if not text:
            continue

        old_words = len(text.split())
        total_old_words += old_words

        # Resegment
        segments = resegment_text(text)

        if len(segments) == 1:
            # No splitting needed, keep original reference
            output_lines.append(f"{ref}\t{segments[0]}")
            total_new_words += len(segments[0].split())
        else:
            # Add sub-numbering
            # Original ref: <jer. ep. X.Y.Z>
            # New refs: <jer. ep. X.Y.Z.1>, <jer. ep. X.Y.Z.2>, ...
            ref_inner = ref[1:-1]  # Strip < >
            for i, seg in enumerate(segments, 1):
                new_ref = f"<{ref_inner}.{i}>"
                output_lines.append(f"{new_ref}\t{seg}")
                total_new_words += len(seg.split())

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in output_lines:
            f.write(line + '\n')

    # Report
    old_count = sum(1 for l in lines if l.strip() and re.match(r'<[^>]+>', l.strip()))
    new_count = len(output_lines)

    print(f"=== Resegmentation Report ===")
    print(f"Old line count:     {old_count}")
    print(f"New line count:     {new_count}")
    print(f"Old avg words/line: {total_old_words / old_count:.1f}")
    print(f"New avg words/line: {total_new_words / new_count:.1f}")
    print(f"Old total words:    {total_old_words}")
    print(f"New total words:    {total_new_words}")

    if total_old_words != total_new_words:
        print(f"WARNING: Word count mismatch! Difference: {total_new_words - total_old_words}")
    else:
        print(f"Word count preserved: OK")

    # Distribution of new line lengths
    new_wcs = [len(l.split('\t')[1].split()) if '\t' in l else 0 for l in output_lines]

    buckets = {}
    for wc in new_wcs:
        if wc <= 5: bucket = '0-5'
        elif wc <= 10: bucket = '6-10'
        elif wc <= 15: bucket = '11-15'
        elif wc <= 20: bucket = '16-20'
        elif wc <= 25: bucket = '21-25'
        elif wc <= 30: bucket = '26-30'
        elif wc <= 40: bucket = '31-40'
        else: bucket = '40+'
        buckets[bucket] = buckets.get(bucket, 0) + 1

    print(f"\nWord count distribution:")
    for bucket in ['0-5', '6-10', '11-15', '16-20', '21-25', '26-30', '31-40', '40+']:
        count = buckets.get(bucket, 0)
        pct = count / new_count * 100
        bar = '#' * int(pct / 2)
        print(f"  {bucket:>5}: {count:5d} ({pct:5.1f}%) {bar}")

    # Check for duplicate references
    refs = [re.match(r'(<[^>]+>)', l).group(1) for l in output_lines if re.match(r'(<[^>]+>)', l)]
    if len(refs) != len(set(refs)):
        from collections import Counter
        dupes = [r for r, c in Counter(refs).items() if c > 1]
        print(f"\nWARNING: {len(dupes)} duplicate references!")
        for d in dupes[:5]:
            print(f"  {d}")
    else:
        print(f"\nAll {len(refs)} references are unique: OK")


if __name__ == '__main__':
    process_file(INPUT_FILE, OUTPUT_FILE)
