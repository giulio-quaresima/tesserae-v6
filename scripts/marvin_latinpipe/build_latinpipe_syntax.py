#!/usr/bin/env python3
"""
LatinPipe Syntax Indexing Script for Marvin Server
===================================================
Builds a syntax index for Latin .tess files using LatinPipe (EvaLatin 2024 winner).
Produces a SQLite database that can be copied back to Replit and merged into
the Tesserae V6 inverted index.

This script is SELF-CONTAINED - it does not depend on any Tesserae backend code.

Usage:
    python build_latinpipe_syntax.py --corpus-dir /path/to/texts/la/
    python build_latinpipe_syntax.py --corpus-dir /path/to/texts/la/ --texts vergil.aeneid.tess
    python build_latinpipe_syntax.py --corpus-dir /path/to/texts/la/ --limit 10
    python build_latinpipe_syntax.py --corpus-dir /path/to/texts/la/ --resume

Requirements:
    pip install requests    (for LatinPipe API mode)
    -- OR --
    LatinPipe local install (for local mode, much faster)

Author: Tesserae V6 Project (Neil Coffee)
Date: February 2026
"""

import os
import sys
import json
import sqlite3
import argparse
import time
import glob
from pathlib import Path


LATINPIPE_API_URL = "https://lindat.mff.cuni.cz/services/udpipe/api/process"
LATINPIPE_MODEL = "latin-evalatin24-240520"


def parse_tess_file(filepath):
    """Parse a .tess file and extract line references and text content."""
    lines = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('<') and '>' in line:
                    ref_end = line.index('>')
                    ref = line[1:ref_end]
                    text = line[ref_end + 1:].strip()
                    if text:
                        lines.append({'ref': ref, 'text': text})
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
    return lines


def parse_conllu(conllu_text):
    """Parse CoNLL-U format output into structured token data."""
    tokens = []
    for line in conllu_text.strip().split('\n'):
        if not line or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) >= 10 and parts[0].isdigit():
            tokens.append({
                'id': int(parts[0]),
                'form': parts[1],
                'lemma': parts[2].lower() if parts[2] else '',
                'upos': parts[3],
                'feats': parts[5] if parts[5] != '_' else '_',
                'head': int(parts[6]) if parts[6] != '_' else 0,
                'deprel': parts[7] if parts[7] != '_' else '',
            })
    return tokens


def parse_with_latinpipe_api(text, max_retries=3):
    """Parse Latin text using LatinPipe REST API."""
    import requests

    for attempt in range(max_retries):
        try:
            response = requests.post(LATINPIPE_API_URL, data={
                'tokenizer': '',
                'tagger': '',
                'parser': '',
                'model': LATINPIPE_MODEL,
                'data': text
            }, timeout=60)

            if response.status_code == 200:
                result = response.json()
                conllu = result.get('result', '')
                return parse_conllu(conllu)
            elif response.status_code == 429:
                wait = 2 ** attempt * 5
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    API error {response.status_code}: {response.text[:100]}")
                return None
        except requests.exceptions.Timeout:
            print(f"    Timeout (attempt {attempt + 1}/{max_retries})")
            time.sleep(2)
        except Exception as e:
            print(f"    API error: {e}")
            return None
    return None


def parse_with_latinpipe_local(text, local_api_url):
    """Parse Latin text using a locally-running LatinPipe server."""
    import requests
    try:
        response = requests.post(local_api_url, data={
            'tokenizer': '',
            'tagger': '',
            'parser': '',
            'data': text
        }, timeout=60)

        if response.status_code == 200:
            result = response.json()
            conllu = result.get('result', '')
            return parse_conllu(conllu)
        else:
            print(f"    Local server error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"    Local parse error: {e}")
        return None


def try_load_local_latinpipe(model_path, repo_path=None, local_port=8100):
    """Start a local LatinPipe server and return connection info, or None.
    
    This starts the latinpipe_evalatin24_server.py on the specified port,
    loads the model once, and keeps it running for fast repeated queries.
    """
    import subprocess

    if not model_path or not os.path.exists(model_path):
        print(f"Model not found at: {model_path}")
        return None

    model_dir = os.path.dirname(model_path)
    model_name = os.path.basename(model_dir)

    if repo_path and os.path.isdir(repo_path):
        search_dirs = [repo_path]
    else:
        search_dirs = [
            os.path.dirname(model_path),
            os.path.dirname(os.path.dirname(model_path)),
        ]

    server_script = None
    for d in search_dirs:
        candidate = os.path.join(d, 'latinpipe_evalatin24_server.py')
        if os.path.exists(candidate):
            server_script = candidate
            break

    if not server_script:
        print("Could not find latinpipe_evalatin24_server.py")
        print("Make sure --repo-path points to the cloned evalatin2024-latinpipe directory.")
        return None

    tokenizer_files = [f for f in os.listdir(model_dir) if f.endswith('.tokenizer')]
    if not tokenizer_files:
        print(f"No .tokenizer file found in {model_dir}")
        print("The LatinPipe server requires a UDPipe tokenizer.")
        print("Falling back to API mode.")
        return None

    variant = tokenizer_files[0].replace('.tokenizer', '')

    local_api_url = f"http://localhost:{local_port}/process"

    print(f"Found LatinPipe server script: {server_script}")
    print(f"  Model dir: {model_dir}")
    print(f"  Variant: {variant}")
    print(f"  Starting local server on port {local_port}...")

    cmd = [
        sys.executable, server_script,
        '--port', str(local_port),
        '--preload_models', 'all',
        '--default_model', model_name,
        '--models', model_name, model_dir, variant, 'LatinPipe',
    ]

    server_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(server_script),
    )

    import requests as req_lib
    print("  Waiting for server to load model (this may take 1-2 minutes)...")
    for attempt in range(120):
        time.sleep(2)
        try:
            r = req_lib.get(f"http://localhost:{local_port}/models", timeout=5)
            if r.status_code == 200:
                print(f"  Server ready! Models: {r.json()}")
                return {
                    'url': local_api_url,
                    'process': server_proc,
                    'port': local_port,
                }
        except req_lib.exceptions.ConnectionError:
            if attempt % 10 == 9:
                print(f"    Still loading... ({(attempt+1)*2}s)")
        except Exception:
            pass

        if server_proc.poll() is not None:
            stdout = server_proc.stdout.read().decode('utf-8', errors='replace')[-500:]
            stderr = server_proc.stderr.read().decode('utf-8', errors='replace')[-500:]
            print(f"  Server exited with code {server_proc.returncode}")
            if stdout.strip():
                print(f"  stdout: {stdout}")
            if stderr.strip():
                print(f"  stderr: {stderr}")
            return None

    print("  Server did not start within 4 minutes. Falling back to API mode.")
    server_proc.terminate()
    return None


def create_syntax_db(output_path):
    """Create the syntax SQLite database with proper schema."""
    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS syntax_source (
            parser TEXT DEFAULT 'latinpipe',
            model TEXT DEFAULT 'evalatin24-240520',
            build_date TEXT,
            total_texts INTEGER DEFAULT 0,
            total_lines INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS texts (
            text_id INTEGER PRIMARY KEY,
            filename TEXT UNIQUE NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS syntax (
            text_id INTEGER NOT NULL,
            ref TEXT NOT NULL,
            tokens TEXT,
            lemmas TEXT,
            upos TEXT,
            heads TEXT,
            deprels TEXT,
            feats TEXT,
            PRIMARY KEY (text_id, ref),
            FOREIGN KEY (text_id) REFERENCES texts(text_id)
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_syntax_text ON syntax(text_id)
    ''')

    conn.commit()
    return conn


def get_processed_texts(conn):
    """Get set of filenames that already have syntax data."""
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT DISTINCT t.filename FROM syntax s 
            JOIN texts t ON s.text_id = t.text_id
        ''')
        return {row[0] for row in cursor.fetchall()}
    except:
        return set()


def store_line_syntax(conn, text_id, ref, tokens):
    """Store parsed syntax data for a single line."""
    if not tokens:
        return False

    try:
        forms = [t['form'] for t in tokens]
        lemmas = [t['lemma'] for t in tokens]
        upos = [t['upos'] for t in tokens]
        heads = [t['head'] for t in tokens]
        deprels = [t['deprel'] for t in tokens]
        feats = [t['feats'] for t in tokens]

        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO syntax (text_id, ref, tokens, lemmas, upos, heads, deprels, feats)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            text_id,
            ref,
            json.dumps(forms),
            json.dumps(lemmas),
            json.dumps(upos),
            json.dumps(heads),
            json.dumps(deprels),
            json.dumps(feats)
        ))
        return True
    except Exception as e:
        print(f"    Storage error: {e}")
        return False


def get_or_create_text_id(conn, filename):
    """Get text_id for a filename, creating if needed."""
    cursor = conn.cursor()
    cursor.execute('SELECT text_id FROM texts WHERE filename = ?', (filename,))
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute('INSERT INTO texts (filename) VALUES (?)', (filename,))
    conn.commit()
    return cursor.lastrowid


def build_syntax_index(corpus_dir, output_path, specific_texts=None,
                       limit=None, resume=True, use_api=True, 
                       model_path=None, repo_path=None,
                       batch_size=10, api_sleep=0.2):
    """
    Build syntax index for Latin .tess files.

    Args:
        corpus_dir: Path to directory containing .tess files
        output_path: Path for output SQLite database
        specific_texts: List of specific .tess filenames to process
        limit: Maximum number of texts to process
        resume: Skip texts that already have syntax data
        use_api: Use LatinPipe REST API (True) or local installation (False)
        model_path: Path to local LatinPipe model (if use_api=False)
        repo_path: Path to cloned LatinPipe repository (if use_api=False)
        batch_size: Lines to batch before committing to database
        api_sleep: Seconds to wait between API requests (default 0.2)
    """
    if not os.path.isdir(corpus_dir):
        print(f"Error: Corpus directory not found: {corpus_dir}")
        sys.exit(1)

    tess_files = sorted(glob.glob(os.path.join(corpus_dir, '*.tess')))
    if not tess_files:
        print(f"Error: No .tess files found in {corpus_dir}")
        sys.exit(1)

    print(f"Found {len(tess_files)} .tess files in {corpus_dir}")

    local_pipeline = None
    if not use_api:
        local_pipeline = try_load_local_latinpipe(model_path, repo_path)
        if not local_pipeline:
            print("Falling back to API mode")
            use_api = True

    if use_api:
        print(f"Using LatinPipe API: {LATINPIPE_API_URL}")
        print(f"Model: {LATINPIPE_MODEL}")
        try:
            import requests
        except ImportError:
            print("Error: 'requests' package required for API mode")
            print("Install with: pip install requests")
            sys.exit(1)

    conn = create_syntax_db(output_path)
    print(f"Output database: {output_path}")

    if specific_texts:
        tess_files = [os.path.join(corpus_dir, f) for f in specific_texts
                      if os.path.exists(os.path.join(corpus_dir, f))]
        print(f"Processing {len(tess_files)} specified texts")

    processed = get_processed_texts(conn) if resume else set()
    if resume and processed:
        before = len(tess_files)
        tess_files = [f for f in tess_files if os.path.basename(f) not in processed]
        skipped = before - len(tess_files)
        if skipped:
            print(f"Resuming: skipping {skipped} already-processed texts")

    if limit:
        tess_files = tess_files[:limit]

    if not tess_files:
        print("No texts to process.")
        return

    print(f"\nProcessing {len(tess_files)} texts...")
    print("=" * 60)

    total_lines = 0
    total_errors = 0
    start_time = time.time()

    for i, filepath in enumerate(tess_files):
        filename = os.path.basename(filepath)
        text_id = get_or_create_text_id(conn, filename)

        lines = parse_tess_file(filepath)
        if not lines:
            print(f"  [{i+1}/{len(tess_files)}] {filename}: no lines found")
            continue

        lines_ok = 0
        lines_fail = 0

        if use_api:
            for j, line_data in enumerate(lines):
                ref = line_data['ref']
                text = line_data['text']
                tokens = parse_with_latinpipe_api(text)
                time.sleep(api_sleep)

                if tokens:
                    if store_line_syntax(conn, text_id, ref, tokens):
                        lines_ok += 1
                    else:
                        lines_fail += 1
                else:
                    lines_fail += 1

                if (j + 1) % batch_size == 0:
                    conn.commit()
        else:
            for j, line_data in enumerate(lines):
                ref = line_data['ref']
                text = line_data['text']
                tokens = parse_with_latinpipe_local(text, local_pipeline['url'])

                if tokens:
                    if store_line_syntax(conn, text_id, ref, tokens):
                        lines_ok += 1
                    else:
                        lines_fail += 1
                else:
                    lines_fail += 1

                if (j + 1) % batch_size == 0:
                    conn.commit()

        conn.commit()
        total_lines += lines_ok
        total_errors += lines_fail

        elapsed = time.time() - start_time
        rate = total_lines / elapsed if elapsed > 0 else 0
        eta_remaining = (len(tess_files) - i - 1) * (elapsed / (i + 1)) if i > 0 else 0

        print(f"  [{i+1}/{len(tess_files)}] {filename}: "
              f"{lines_ok}/{len(lines)} lines OK "
              f"({rate:.1f} lines/s, ETA: {format_time(eta_remaining)})")

    cursor = conn.cursor()
    import datetime
    cursor.execute('''
        INSERT OR REPLACE INTO syntax_source (parser, model, build_date, total_texts, total_lines)
        VALUES (?, ?, ?, ?, ?)
    ''', ('latinpipe', LATINPIPE_MODEL, datetime.datetime.now().isoformat(),
          len(tess_files), total_lines))
    conn.commit()
    conn.close()

    if not use_api and local_pipeline and 'process' in local_pipeline:
        print("\nShutting down local LatinPipe server...")
        local_pipeline['process'].terminate()
        local_pipeline['process'].wait(timeout=10)

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("SYNTAX INDEXING COMPLETE")
    print(f"  Texts processed: {len(tess_files)}")
    print(f"  Lines indexed:   {total_lines}")
    print(f"  Errors:          {total_errors}")
    print(f"  Time elapsed:    {format_time(elapsed)}")
    print(f"  Output file:     {output_path}")
    print(f"\nCopy {output_path} to your Replit project and run the merge script.")


def format_time(seconds):
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.0f}m {seconds%60:.0f}s"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"


def main():
    parser = argparse.ArgumentParser(
        description='Build LatinPipe syntax index for Latin .tess files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Index all Latin texts using API
  python build_latinpipe_syntax.py --corpus-dir /path/to/texts/la/

  # Index specific texts
  python build_latinpipe_syntax.py --corpus-dir /path/to/texts/la/ \\
      --texts vergil.aeneid.tess lucan.bellum_civile.tess

  # Test with first 5 texts
  python build_latinpipe_syntax.py --corpus-dir /path/to/texts/la/ --limit 5

  # Resume interrupted build (default behavior, just re-run same command)
  python build_latinpipe_syntax.py --corpus-dir /path/to/texts/la/

  # Use local LatinPipe installation (much faster)
  python build_latinpipe_syntax.py --corpus-dir /path/to/texts/la/ \\
      --local --model-path /path/to/model.weights.h5 \\
      --repo-path /path/to/evalatin2024-latinpipe/

  # Slow down API requests to avoid rate limiting
  python build_latinpipe_syntax.py --corpus-dir /path/to/texts/la/ --sleep 1.0
        """
    )
    parser.add_argument('--corpus-dir', required=True,
                        help='Path to directory containing .tess files')
    parser.add_argument('--output', default='syntax_latin.db',
                        help='Output SQLite database path (default: syntax_latin.db)')
    parser.add_argument('--texts', nargs='+',
                        help='Specific .tess filenames to process')
    parser.add_argument('--limit', type=int,
                        help='Maximum number of texts to process')
    parser.add_argument('--no-resume', action='store_true',
                        help='Reprocess all texts from scratch (default: resume from last run)')
    parser.add_argument('--local', action='store_true',
                        help='Use local LatinPipe installation instead of API')
    parser.add_argument('--model-path',
                        help='Path to local LatinPipe model weights (.h5 file)')
    parser.add_argument('--repo-path',
                        help='Path to cloned evalatin2024-latinpipe repository')
    parser.add_argument('--batch-size', type=int, default=10,
                        help='Lines to batch before DB commit (default: 10)')
    parser.add_argument('--sleep', type=float, default=0.2,
                        help='Seconds between API requests to avoid rate limiting (default: 0.2)')

    args = parser.parse_args()

    build_syntax_index(
        corpus_dir=args.corpus_dir,
        output_path=args.output,
        specific_texts=args.texts,
        limit=args.limit,
        resume=not args.no_resume,
        use_api=not args.local,
        model_path=args.model_path,
        repo_path=args.repo_path,
        batch_size=args.batch_size,
        api_sleep=args.sleep
    )


if __name__ == '__main__':
    main()
