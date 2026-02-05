#!/usr/bin/env python3
"""
Build syntax index for dependency parsing data.
Parses corpus texts using Stanza and stores dependency structures in SQLite.

Usage:
    python scripts/build_syntax_index.py --language la
    python scripts/build_syntax_index.py --language la --texts vergil.aeneid.tess lucan.bellum_civile.tess
    python scripts/build_syntax_index.py --language la --limit 10  # Process first 10 texts
"""
import os
import sys
import json
import sqlite3
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.syntax_parser import (
    StanzaParser, 
    ensure_syntax_table, 
    store_syntax_for_line,
    get_syntax_stats,
    SyntaxSentence,
    SyntaxToken
)

TEXTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')
INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'inverted_index')


def get_text_files(language):
    """Get all .tess files for a language"""
    lang_dir = os.path.join(TEXTS_DIR, language)
    if not os.path.exists(lang_dir):
        return []
    return sorted([f for f in os.listdir(lang_dir) if f.endswith('.tess')])


def parse_tess_file(filepath):
    """Parse a .tess file and extract line references and content"""
    lines = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Parse format: <reference> text content
                if line.startswith('<') and '>' in line:
                    ref_end = line.index('>')
                    ref = line[1:ref_end]
                    text = line[ref_end + 1:].strip()
                    if text:
                        lines.append({'ref': ref, 'text': text})
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    
    return lines


def get_existing_texts(language):
    """Get list of text_ids and filenames from the index"""
    db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
    if not os.path.exists(db_path):
        return {}
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT text_id, filename FROM texts')
    texts = {row[1]: row[0] for row in cursor.fetchall()}
    conn.close()
    return texts


def get_texts_with_syntax(language):
    """Get set of text_ids that already have syntax data"""
    db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
    if not os.path.exists(db_path):
        return set()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='syntax'")
        if not cursor.fetchone():
            conn.close()
            return set()
        
        cursor.execute('SELECT DISTINCT text_id FROM syntax')
        text_ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        return text_ids
    except:
        return set()


def build_syntax_index(language, specific_texts=None, limit=None, resume=True, verbose=True):
    """
    Build syntax index for a language.
    
    Args:
        language: 'la', 'grc', or 'en'
        specific_texts: List of specific .tess filenames to process (optional)
        limit: Maximum number of texts to process (optional)
        resume: Skip texts that already have syntax data
        verbose: Print progress messages
    """
    # Ensure syntax table exists
    if not ensure_syntax_table(language):
        print(f"Failed to create syntax table for {language}")
        return
    
    # Get indexed texts
    text_mapping = get_existing_texts(language)
    if not text_mapping:
        print(f"No texts found in {language} index. Run build_inverted_index.py first.")
        return
    
    # Get texts already processed
    processed_texts = get_texts_with_syntax(language) if resume else set()
    
    # Determine which texts to process
    if specific_texts:
        filenames = [f for f in specific_texts if f in text_mapping]
    else:
        filenames = list(text_mapping.keys())
    
    # Filter out already processed
    if resume and processed_texts:
        original_count = len(filenames)
        filenames = [f for f in filenames if text_mapping[f] not in processed_texts]
        if verbose and original_count != len(filenames):
            print(f"Resuming: {original_count - len(filenames)} texts already processed")
    
    # Apply limit
    if limit:
        filenames = filenames[:limit]
    
    if not filenames:
        print(f"No texts to process for {language}")
        stats = get_syntax_stats(language)
        if stats:
            print(f"Current syntax data: {stats['line_count']} lines from {stats['text_count']} texts")
        return
    
    if verbose:
        print(f"Building syntax index for {language}: {len(filenames)} texts")
    
    # Initialize Stanza parser
    parser = StanzaParser()
    
    total_lines = 0
    total_errors = 0
    
    for i, filename in enumerate(filenames):
        text_id = text_mapping[filename]
        filepath = os.path.join(TEXTS_DIR, language, filename)
        
        if not os.path.exists(filepath):
            if verbose:
                print(f"  File not found: {filename}")
            continue
        
        # Parse .tess file
        lines = parse_tess_file(filepath)
        if not lines:
            continue
        
        lines_processed = 0
        lines_failed = 0
        
        for line_data in lines:
            ref = line_data['ref']
            text = line_data['text']
            
            # Parse with Stanza
            syntax_sent = parser.parse(text, language)
            
            if syntax_sent:
                # Store in database
                if store_syntax_for_line(text_id, ref, syntax_sent, language):
                    lines_processed += 1
                else:
                    lines_failed += 1
            else:
                lines_failed += 1
        
        total_lines += lines_processed
        total_errors += lines_failed
        
        if verbose and (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(filenames)} texts ({total_lines} lines)...")
    
    # Save Stanza cache
    parser.save()
    
    # Print final stats
    if verbose:
        stats = get_syntax_stats(language)
        print(f"\nSyntax indexing complete for {language}:")
        print(f"  Processed: {total_lines} lines")
        print(f"  Errors: {total_errors} lines")
        if stats:
            print(f"  Total in index: {stats['line_count']} lines from {stats['text_count']} texts")


def main():
    parser = argparse.ArgumentParser(description='Build syntax index for dependency parsing')
    parser.add_argument('--language', '-l', choices=['la', 'grc', 'en'], default='la',
                       help='Language to process (default: la)')
    parser.add_argument('--texts', '-t', nargs='+', 
                       help='Specific .tess files to process')
    parser.add_argument('--limit', type=int,
                       help='Maximum number of texts to process')
    parser.add_argument('--no-resume', action='store_true',
                       help='Reprocess all texts (ignore existing data)')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Suppress progress messages')
    
    args = parser.parse_args()
    
    build_syntax_index(
        language=args.language,
        specific_texts=args.texts,
        limit=args.limit,
        resume=not args.no_resume,
        verbose=not args.quiet
    )


if __name__ == '__main__':
    main()
