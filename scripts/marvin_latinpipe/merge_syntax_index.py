#!/usr/bin/env python3
"""
Merge LatinPipe Syntax Index into Tesserae V6 Inverted Index
=============================================================
After building the syntax index on Marvin with build_latinpipe_syntax.py,
copy the resulting syntax_latin.db file to Replit and run this script
to merge it into the main la_index.db.

Usage (run from Tesserae project root on Replit):
    python scripts/marvin_latinpipe/merge_syntax_index.py syntax_latin.db

Author: Tesserae V6 Project (Neil Coffee)
Date: February 2026
"""

import os
import sys
import json
import sqlite3
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
INDEX_DIR = PROJECT_ROOT / 'data' / 'inverted_index'


def merge_syntax_data(source_db_path, language='la', dry_run=False):
    """
    Merge syntax data from a LatinPipe-built database into the main index.
    
    Args:
        source_db_path: Path to the syntax_latin.db from Marvin
        language: Language code (default: 'la')
        dry_run: If True, report what would happen without making changes
    """
    target_db_path = INDEX_DIR / f'{language}_index.db'
    
    if not os.path.exists(source_db_path):
        print(f"Error: Source database not found: {source_db_path}")
        sys.exit(1)
    
    if not os.path.exists(target_db_path):
        print(f"Error: Target index not found: {target_db_path}")
        sys.exit(1)
    
    source_conn = sqlite3.connect(source_db_path)
    target_conn = sqlite3.connect(str(target_db_path))
    
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()
    
    try:
        source_cursor.execute('SELECT parser, model, build_date, total_texts, total_lines FROM syntax_source')
        source_info = source_cursor.fetchone()
        if source_info:
            print(f"Source: {source_info[0]} ({source_info[1]})")
            print(f"Built:  {source_info[2]}")
            print(f"Data:   {source_info[3]} texts, {source_info[4]} lines")
    except:
        print("Source: Unknown (no metadata)")
    
    target_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='syntax'")
    if not target_cursor.fetchone():
        target_cursor.execute('''
            CREATE TABLE syntax (
                text_id INTEGER NOT NULL,
                ref TEXT NOT NULL,
                tokens TEXT,
                lemmas TEXT,
                upos TEXT,
                heads TEXT,
                deprels TEXT,
                feats TEXT,
                PRIMARY KEY (text_id, ref)
            )
        ''')
        target_cursor.execute('CREATE INDEX IF NOT EXISTS idx_syntax_text ON syntax(text_id)')
        target_conn.commit()
        print("Created syntax table in target index")
    
    target_cursor.execute('SELECT text_id, filename FROM texts')
    target_texts = {row[1]: row[0] for row in target_cursor.fetchall()}
    print(f"\nTarget index has {len(target_texts)} texts")
    
    source_cursor.execute('SELECT text_id, filename FROM texts')
    source_texts = {row[1]: row[0] for row in source_cursor.fetchall()}
    print(f"Source index has {len(source_texts)} texts")
    
    matched = 0
    unmatched = []
    total_lines = 0
    total_replaced = 0
    total_new = 0
    
    for source_filename, source_text_id in source_texts.items():
        if source_filename not in target_texts:
            unmatched.append(source_filename)
            continue
        
        matched += 1
        target_text_id = target_texts[source_filename]
        
        source_cursor.execute(
            'SELECT ref, tokens, lemmas, upos, heads, deprels, feats FROM syntax WHERE text_id = ?',
            (source_text_id,)
        )
        rows = source_cursor.fetchall()
        
        if not rows:
            continue
        
        for row in rows:
            ref, tokens, lemmas, upos, heads, deprels, feats = row
            
            if not dry_run:
                target_cursor.execute(
                    'SELECT 1 FROM syntax WHERE text_id = ? AND ref = ?',
                    (target_text_id, ref)
                )
                exists = target_cursor.fetchone()
                
                target_cursor.execute('''
                    INSERT OR REPLACE INTO syntax (text_id, ref, tokens, lemmas, upos, heads, deprels, feats)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (target_text_id, ref, tokens, lemmas, upos, heads, deprels, feats))
                
                if exists:
                    total_replaced += 1
                else:
                    total_new += 1
            
            total_lines += 1
        
        if not dry_run and matched % 50 == 0:
            target_conn.commit()
    
    if not dry_run:
        target_conn.commit()
    
    print(f"\n{'DRY RUN - ' if dry_run else ''}MERGE RESULTS:")
    print(f"  Texts matched:   {matched}")
    print(f"  Texts unmatched: {len(unmatched)}")
    print(f"  Lines processed: {total_lines}")
    if not dry_run:
        print(f"  Lines new:       {total_new}")
        print(f"  Lines replaced:  {total_replaced}")
    
    if unmatched:
        print(f"\n  Unmatched texts (in source but not in target index):")
        for f in unmatched[:10]:
            print(f"    - {f}")
        if len(unmatched) > 10:
            print(f"    ... and {len(unmatched) - 10} more")
    
    target_cursor.execute('SELECT COUNT(DISTINCT text_id), COUNT(*) FROM syntax')
    stats = target_cursor.fetchone()
    print(f"\n  Target index now has: {stats[0]} texts with syntax, {stats[1]} total lines")
    
    source_conn.close()
    target_conn.close()
    
    if not dry_run:
        print(f"\nMerge complete! Syntax data integrated into {target_db_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Merge LatinPipe syntax index into Tesserae V6 inverted index',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview what would happen (no changes made)
  python scripts/marvin_latinpipe/merge_syntax_index.py syntax_latin.db --dry-run

  # Merge the data
  python scripts/marvin_latinpipe/merge_syntax_index.py syntax_latin.db

  # Merge Greek syntax data
  python scripts/marvin_latinpipe/merge_syntax_index.py syntax_greek.db --language grc
        """
    )
    parser.add_argument('source_db', help='Path to the syntax database from Marvin')
    parser.add_argument('--language', default='la', choices=['la', 'grc', 'en'],
                        help='Language code (default: la)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without modifying anything')
    
    args = parser.parse_args()
    merge_syntax_data(args.source_db, args.language, args.dry_run)


if __name__ == '__main__':
    main()
