#!/usr/bin/env python3
"""
Build an inverted index for fast lemma-based searches.
Maps lemma → list of (text_id, line_ref, positions) for instant lookups.

For Latin, can optionally use LatinPipe syntax database (syntax_latin.db) to get
high-quality lemmatizations from the EvaLatin 2024 parser, falling back to the
text_processor for texts not covered by the syntax database.
"""
import os
import sys
import json
import sqlite3
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from backend.text_processor import TextProcessor

TEXTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')
INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'inverted_index')


def load_syntax_data(language):
    """Load LatinPipe syntax data for use during index build.
    Returns a dict mapping (filename_stem, locus) -> (tokens, lemmas) or None."""
    if language != 'la':
        return None
    syntax_db = os.path.join(INDEX_DIR, 'syntax_latin.db')
    if not os.path.exists(syntax_db):
        return None
    try:
        conn = sqlite3.connect(syntax_db)
        cursor = conn.cursor()
        cursor.execute('SELECT text_id, locus, tokens, lemmas FROM syntax')
        data = {}
        count = 0
        for row in cursor:
            text_id, locus, tokens_json, lemmas_json = row
            toks = json.loads(tokens_json) if tokens_json.startswith('[') else tokens_json.split()
            lems = json.loads(lemmas_json) if lemmas_json.startswith('[') else lemmas_json.split()
            norm_lems = [l.lower().replace('j', 'i').replace('v', 'u') for l in lems]
            data[(text_id, locus)] = (toks, norm_lems)
            count += 1
        conn.close()
        print(f"  Loaded {count} lines from LatinPipe syntax database")
        return data
    except Exception as e:
        print(f"  Could not load syntax data: {e}")
        return None

def get_text_files(language):
    """Get all .tess files for a language"""
    lang_dir = os.path.join(TEXTS_DIR, language)
    if not os.path.exists(lang_dir):
        return []
    return [f for f in os.listdir(lang_dir) if f.endswith('.tess')]

def build_index(language, text_processor, verbose=True, resume=True):
    """Build inverted index for a language (resumable by default)"""
    os.makedirs(INDEX_DIR, exist_ok=True)
    db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
    
    existing_files = set()
    
    if os.path.exists(db_path) and resume:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT filename FROM texts')
            existing_files = {row[0] for row in cursor.fetchall()}
            if verbose and existing_files:
                print(f"  Resuming: {len(existing_files)} files already indexed")
            conn.close()
        except:
            pass
    
    if not os.path.exists(db_path) or not existing_files:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS texts (
                text_id INTEGER PRIMARY KEY,
                filename TEXT UNIQUE,
                author TEXT,
                title TEXT,
                line_count INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS postings (
                lemma TEXT,
                text_id INTEGER,
                ref TEXT,
                positions TEXT,
                FOREIGN KEY (text_id) REFERENCES texts(text_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lines (
                text_id INTEGER,
                ref TEXT,
                content TEXT,
                lemmas TEXT,
                tokens TEXT,
                PRIMARY KEY (text_id, ref),
                FOREIGN KEY (text_id) REFERENCES texts(text_id)
            )
        ''')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_lemma ON postings(lemma)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_text ON postings(text_id)')
        conn.commit()
        conn.close()
    else:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lines (
                text_id INTEGER,
                ref TEXT,
                content TEXT,
                lemmas TEXT,
                tokens TEXT,
                PRIMARY KEY (text_id, ref),
                FOREIGN KEY (text_id) REFERENCES texts(text_id)
            )
        ''')
        conn.commit()
        conn.close()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    text_files = get_text_files(language)
    files_to_process = [f for f in text_files if f not in existing_files]
    total_files = len(text_files)
    remaining = len(files_to_process)
    total_postings = 0
    
    if verbose:
        if existing_files:
            print(f"Building index for {language}: {remaining} remaining of {total_files} files")
        else:
            print(f"Building index for {language}: {total_files} files")
    
    for i, filename in enumerate(files_to_process):
        filepath = os.path.join(TEXTS_DIR, language, filename)
        
        try:
            units = text_processor.process_file(filepath, language, unit_type='line')
        except Exception as e:
            if verbose:
                print(f"  Error processing {filename}: {e}")
            continue
        
        parts = filename.replace('.tess', '').split('.')
        author = parts[0] if parts else ''
        title = '.'.join(parts[1:]) if len(parts) > 1 else ''
        
        cursor.execute(
            'INSERT OR IGNORE INTO texts (filename, author, title, line_count) VALUES (?, ?, ?, ?)',
            (filename, author, title, len(units))
        )
        if cursor.rowcount == 0:
            cursor.execute('SELECT text_id FROM texts WHERE filename = ?', (filename,))
            text_id = cursor.fetchone()[0]
            continue
        text_id = cursor.lastrowid
        
        for unit in units:
            ref = unit.get('ref', '')
            lemmas = unit.get('lemmas', [])
            tokens = unit.get('tokens', [])
            text_content = unit.get('text', '')
            
            lemma_positions = {}
            for pos, lemma in enumerate(lemmas):
                if lemma not in lemma_positions:
                    lemma_positions[lemma] = []
                lemma_positions[lemma].append(pos)
            
            for lemma, positions in lemma_positions.items():
                cursor.execute(
                    'INSERT INTO postings (lemma, text_id, ref, positions) VALUES (?, ?, ?, ?)',
                    (lemma, text_id, ref, json.dumps(positions))
                )
                total_postings += 1
            
            cursor.execute(
                'INSERT OR IGNORE INTO lines (text_id, ref, content, lemmas, tokens) VALUES (?, ?, ?, ?, ?)',
                (text_id, ref, text_content, json.dumps(lemmas), json.dumps(tokens))
            )
        
        if (i + 1) % 50 == 0:
            conn.commit()
            if verbose:
                print(f"  Processed {i + 1}/{remaining} files...")
    
    conn.commit()
    
    cursor.execute('SELECT COUNT(DISTINCT lemma) FROM postings')
    unique_lemmas = cursor.fetchone()[0]
    
    conn.close()
    
    file_size = os.path.getsize(db_path) / (1024 * 1024)
    
    if verbose:
        print(f"  Completed: {total_files} texts, {unique_lemmas} unique lemmas, {total_postings} postings")
        print(f"  Index size: {file_size:.1f} MB")
        print(f"  Saved to: {db_path}")
    
    return db_path

def main():
    parser = argparse.ArgumentParser(description='Build inverted index for Tesserae corpus')
    parser.add_argument('--language', '-l', choices=['la', 'grc', 'en', 'all'], default='all',
                        help='Language to index (default: all)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress output')
    args = parser.parse_args()
    
    text_processor = TextProcessor()
    
    if args.language == 'all':
        languages = ['la', 'grc', 'en']
    else:
        languages = [args.language]
    
    for lang in languages:
        build_index(lang, text_processor, verbose=not args.quiet)
        print()
    
    print("Done!")

if __name__ == '__main__':
    main()
