#!/usr/bin/env python3
"""Run Tesserae V6 dev server on port 5001 (view via SSH tunnel)."""
import os
import sys

_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(_root)
sys.path.insert(0, _root)

# Load .env before importing app (app reads DATABASE_URL etc. at import time)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_root, '.env'))
except ImportError:
    pass  # dotenv not installed, rely on system env

# Dev server has no Apache; frontend expects /api/*. Force API_PREFIX so /api/texts etc. work.
os.environ["API_PREFIX"] = "/api"

from backend.app import app, start_cache_init

if __name__ == '__main__':
    try:
        start_cache_init()
    except Exception as e:
        print(f'Warning: Cache init failed (non-fatal): {e}')
    app.run(host='127.0.0.1', port=5001, debug=True, threaded=True)
