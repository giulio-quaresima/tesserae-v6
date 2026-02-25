#!/usr/bin/env python3
"""
Rebuild lemma cache for all texts using multiprocessing.
Skips texts that are already cached with valid file hashes.

Usage:
    python scripts/rebuild_lemma_cache.py          # all languages
    python scripts/rebuild_lemma_cache.py la        # just Latin
    python scripts/rebuild_lemma_cache.py --force   # rebuild even if cached
"""
import sys
import os
import time
import multiprocessing as mp
from functools import partial

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['TESSERAE_DIRECT_SERVER'] = '1'

from backend.lemma_cache import (
    get_cache_path, get_file_hash, save_cached_units,
    get_cached_units, get_cache_stats, TEXTS_DIR
)


def process_one_text(args):
    """Process a single text file. Each worker loads its own TextProcessor."""
    text_file, language, force = args
    # Import inside worker so each process gets its own instance
    from backend.text_processor import TextProcessor

    # Use a per-process cached TextProcessor
    if not hasattr(process_one_text, '_tp'):
        process_one_text._tp = TextProcessor()
    tp = process_one_text._tp

    filepath = os.path.join(TEXTS_DIR, language, text_file)
    if not os.path.exists(filepath):
        return ('skip', text_file, 'file not found')

    # Check if already cached and valid
    if not force:
        cached = get_cached_units(text_file, language)
        if cached is not None:
            return ('cached', text_file, '')

    try:
        file_hash = get_file_hash(filepath)
        units_line = tp.process_file(filepath, language, 'line')
        units_phrase = tp.process_file(filepath, language, 'phrase')
        save_cached_units(text_file, language, units_line, units_phrase, file_hash)
        return ('ok', text_file, f'{len(units_line)} lines')
    except Exception as e:
        return ('error', text_file, str(e))


def rebuild_language(language, force=False, workers=16):
    """Rebuild cache for one language using multiprocessing."""
    lang_dir = os.path.join(TEXTS_DIR, language)
    if not os.path.exists(lang_dir):
        print(f"  No texts directory for {language}")
        return

    text_files = sorted([f for f in os.listdir(lang_dir) if f.endswith('.tess')])
    total = len(text_files)
    print(f"\n{'='*60}")
    print(f"  {language.upper()}: {total} texts, {workers} workers")
    print(f"{'='*60}")

    args_list = [(f, language, force) for f in text_files]

    start = time.time()
    processed = 0
    skipped = 0
    errors = []

    with mp.Pool(workers) as pool:
        for i, result in enumerate(pool.imap_unordered(process_one_text, args_list)):
            status, text_file, detail = result
            if status == 'ok':
                processed += 1
                if processed % 20 == 0 or processed == 1:
                    elapsed = time.time() - start
                    rate = processed / elapsed if elapsed > 0 else 0
                    remaining = (total - i - 1) / rate if rate > 0 else 0
                    print(f"  [{i+1}/{total}] {text_file} — {detail} "
                          f"({rate:.1f}/s, ~{remaining/60:.0f}m left)")
            elif status == 'cached':
                skipped += 1
            elif status == 'error':
                errors.append(f"{text_file}: {detail}")
                print(f"  ERROR: {text_file}: {detail}")

    elapsed = time.time() - start
    print(f"\n  Done in {elapsed:.0f}s: {processed} built, {skipped} already cached, {len(errors)} errors")
    if errors:
        print(f"  First 5 errors:")
        for e in errors[:5]:
            print(f"    {e}")


def main():
    force = '--force' in sys.argv
    languages = [a for a in sys.argv[1:] if a != '--force']
    if not languages:
        languages = ['la', 'grc', 'en']

    # Use 4 workers max — each loads CLTK models (~500MB), so 4 × 500MB = ~2GB.
    # Previous run with 16 workers crashed Marvin (16 × 500MB = 8GB+ OOM).
    workers = min(4, mp.cpu_count())

    print("Lemma Cache Rebuild")
    print(f"  Workers: {workers}")
    print(f"  Force rebuild: {force}")

    # Show stats before
    stats = get_cache_stats()
    print("\nBEFORE:")
    for lang, s in stats.items():
        print(f"  {lang}: {s['cached']}/{s['total']} ({s['coverage']})")

    for lang in languages:
        rebuild_language(lang, force=force, workers=workers)

    # Show stats after
    stats = get_cache_stats()
    print("\nAFTER:")
    for lang, s in stats.items():
        print(f"  {lang}: {s['cached']}/{s['total']} ({s['coverage']})")

    print("\nDone!")


if __name__ == '__main__':
    main()
