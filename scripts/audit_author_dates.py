#!/usr/bin/env python3
"""Audit author_dates.json against .tess corpus files.

Reports:
  (a) Missing author keys (in .tess filenames but not in author_dates.json)
  (b) Count of affected texts per missing key
  (c) Possible name-variation matches (fuzzy)

Usage:
  python scripts/audit_author_dates.py
"""

import json
import os
import sys
from collections import defaultdict
from difflib import SequenceMatcher

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTHOR_DATES_PATH = os.path.join(BASE_DIR, "backend", "author_dates.json")
TEXTS_DIR = os.path.join(BASE_DIR, "texts")

LANGUAGES = {
    "la": "Latin",
    "grc": "Greek",
    "en": "English",
}

# Keys we expect to have null dates (skip from "missing" report)
EXPECTED_NULL = {"unknown", "anonymous", "anonymi", "anonymus", "test", "glass", "couplet_et_alii"}


def extract_author_key(filename):
    """Extract author key from .tess filename (first dot-delimited segment)."""
    return filename.split(".")[0]


def find_similar_keys(missing_key, existing_keys, threshold=0.6):
    """Find existing keys that are similar to a missing key."""
    matches = []
    for existing in existing_keys:
        ratio = SequenceMatcher(None, missing_key, existing).ratio()
        if ratio >= threshold:
            matches.append((existing, ratio))
    matches.sort(key=lambda x: -x[1])
    return matches[:3]


def main():
    with open(AUTHOR_DATES_PATH, "r") as f:
        author_dates = json.load(f)

    total_missing_texts = 0
    total_missing_keys = 0

    for lang_code, lang_name in LANGUAGES.items():
        lang_dir = os.path.join(TEXTS_DIR, lang_code)
        if not os.path.isdir(lang_dir):
            print(f"\n--- {lang_name} ({lang_code}) ---")
            print(f"  Directory not found: {lang_dir}")
            continue

        # Get all .tess files and extract author keys
        tess_files = [f for f in os.listdir(lang_dir) if f.endswith(".tess")]
        author_texts = defaultdict(list)
        for f in tess_files:
            key = extract_author_key(f)
            author_texts[key].append(f)

        # Get existing keys in author_dates.json for this language
        existing_keys = set(author_dates.get(lang_code, {}).keys())
        corpus_keys = set(author_texts.keys())

        # Find missing keys
        missing_keys = corpus_keys - existing_keys

        # Filter out empty keys and expected nulls
        missing_keys = {k for k in missing_keys if k and k not in EXPECTED_NULL}

        # Count texts
        total_texts = len(tess_files)
        missing_text_count = sum(len(author_texts[k]) for k in missing_keys)
        # Also count empty-key texts
        empty_key_texts = author_texts.get("", [])

        print(f"\n{'='*60}")
        print(f"  {lang_name} ({lang_code})")
        print(f"{'='*60}")
        print(f"  Total .tess files: {total_texts}")
        print(f"  Unique author keys: {len(corpus_keys)}")
        print(f"  Keys in author_dates.json: {len(existing_keys)}")
        print(f"  Missing keys: {len(missing_keys)}")
        print(f"  Affected texts: {missing_text_count} ({missing_text_count/total_texts*100:.1f}%)")

        if empty_key_texts:
            print(f"\n  MALFORMED (empty author key): {len(empty_key_texts)} files")
            for f in sorted(empty_key_texts):
                print(f"    - {f}")

        if missing_keys:
            print(f"\n  Missing author keys:")
            for key in sorted(missing_keys):
                texts = author_texts[key]
                similar = find_similar_keys(key, existing_keys)
                similar_str = ""
                if similar:
                    best = similar[0]
                    if best[1] >= 0.7:
                        similar_str = f"  <-- possible match: {best[0]} ({best[1]:.0%})"
                print(f"    {key:45s} ({len(texts):3d} texts){similar_str}")

            total_missing_texts += missing_text_count
            total_missing_keys += len(missing_keys)
        else:
            print(f"\n  All author keys covered!")

    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total missing keys: {total_missing_keys}")
    print(f"  Total affected texts: {total_missing_texts}")


if __name__ == "__main__":
    main()
