#!/usr/bin/env python3
"""
Automated endpoint tests for Tesserae V6 dev server.
Tests all major website functions against localhost:5000.

Usage:
    python tests/test_endpoints.py
"""

import requests
import json
import sys
import time

BASE = "http://localhost:5000"
PASS = 0
FAIL = 0
ERRORS = []


def test(name, fn):
    global PASS, FAIL, ERRORS
    try:
        result = fn()
        if result:
            PASS += 1
            print(f"  PASS  {name}")
        else:
            FAIL += 1
            ERRORS.append(name)
            print(f"  FAIL  {name}")
    except Exception as e:
        FAIL += 1
        ERRORS.append(f"{name}: {e}")
        print(f"  FAIL  {name}: {e}")


def check_json(resp, min_keys=None):
    """Verify response is valid JSON with expected keys."""
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    if min_keys:
        for k in min_keys:
            assert k in data, f"Missing key '{k}' in response"
    return data


# ── Corpus & Text APIs ──────────────────────────────────────────────

print("\n=== Corpus & Text APIs ===")

test("GET /api/authors?language=la", lambda: (
    len(check_json(requests.get(f"{BASE}/api/authors?language=la"))) > 100
))

test("GET /api/authors?language=grc", lambda: (
    len(check_json(requests.get(f"{BASE}/api/authors?language=grc"))) > 50
))

test("GET /api/texts?language=la", lambda: (
    len(check_json(requests.get(f"{BASE}/api/texts?language=la"))) > 500
))

test("GET /api/texts?language=en", lambda: (
    len(check_json(requests.get(f"{BASE}/api/texts?language=en"))) > 5
))

test("GET /api/text/<id> (Aeneid)", lambda: (
    'lines' in check_json(requests.get(f"{BASE}/api/text/vergil.aeneid.tess"))
))


# ── Line Search ─────────────────────────────────────────────────────

print("\n=== Line Search ===")

test("POST /api/line-search (arma virumque cano, la)", lambda: (
    check_json(requests.post(f"{BASE}/api/line-search", json={
        "query": "arma virumque cano", "language": "la"
    })).get('total', 0) > 0
))

test("POST /api/line-search (menin aeide thea, grc)", lambda: (
    check_json(requests.post(f"{BASE}/api/line-search", json={
        "query": "μῆνιν ἄειδε θεά", "language": "grc"
    })).get('total', 0) >= 0  # May return 0 if index missing, but shouldn't error
))

test("POST /api/line-search (exact search)", lambda: (
    check_json(requests.post(f"{BASE}/api/line-search", json={
        "query": "arma virumque", "language": "la", "search_type": "exact"
    })).get('total', 0) >= 0
))


# ── Pairwise Search (SSE streaming) ────────────────────────────────

print("\n=== Pairwise Search (regular) ===")

def test_sse_search(endpoint, payload, expect_results=True):
    """Test an SSE streaming search endpoint."""
    resp = requests.post(f"{BASE}{endpoint}", json=payload, stream=True, timeout=120)
    assert resp.status_code == 200, f"HTTP {resp.status_code}"

    events = []
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data: "):
            data = json.loads(line[6:])
            events.append(data)
            if data.get('type') in ('complete', 'error'):
                break

    assert len(events) > 0, "No SSE events received"
    last = events[-1]
    if last.get('type') == 'error':
        raise AssertionError(f"Search error: {last.get('message')}")
    assert last.get('type') == 'complete', f"Last event type: {last.get('type')}"

    if expect_results:
        results = last.get('results', [])
        assert len(results) > 0, "No results in complete event"
    return last

test("Lemma search: Lucan BC 1 × Vergil Aen 1", lambda: (
    test_sse_search("/api/search-stream", {
        "source": "lucan.bellum_civile.part.1.tess",
        "target": "vergil.aeneid.part.1.tess",
        "language": "la",
        "match_type": "lemma",
        "min_matches": 2,
        "stoplist_size": 0,
        "stoplist_basis": "source_target",
        "source_unit_type": "line",
        "target_unit_type": "line",
        "max_distance": 999,
        "max_results": 100
    }) is not None
))

test("Exact search: Lucan BC 1 × Vergil Aen 1", lambda: (
    test_sse_search("/api/search-stream", {
        "source": "lucan.bellum_civile.part.1.tess",
        "target": "vergil.aeneid.part.1.tess",
        "language": "la",
        "match_type": "exact",
        "min_matches": 2,
        "stoplist_size": 0,
        "stoplist_basis": "source_target",
        "source_unit_type": "line",
        "target_unit_type": "line",
        "max_distance": 999,
        "max_results": 100
    }) is not None
))


# ── Fusion Search (SSE streaming) ──────────────────────────────────

print("\n=== Fusion Search ===")

test("Fusion search: Lucan BC 1 × Vergil Aen 1", lambda: (
    test_sse_search("/api/search-fusion", {
        "source": "lucan.bellum_civile.part.1.tess",
        "target": "vergil.aeneid.part.1.tess",
        "language": "la",
        "mode": "merged",
        "max_results": 100,
        "source_unit_type": "line",
        "target_unit_type": "line",
        "use_meter": False
    }) is not None
))


# ── Corpus Search ──────────────────────────────────────────────────

print("\n=== Corpus Search ===")

test("POST /api/corpus-search (arma + uir, la)", lambda: (
    check_json(requests.post(f"{BASE}/api/corpus-search", json={
        "lemmas": ["arma", "uir"],
        "language": "la"
    })).get('total', 0) > 0
))

test("POST /api/corpus-search (single lemma, la)", lambda: (
    check_json(requests.post(f"{BASE}/api/corpus-search", json={
        "lemmas": ["arma"],
        "language": "la"
    })).get('total', 0) > 0
))


# ── Rare Words / Bigrams ───────────────────────────────────────────

print("\n=== Rare Words & Bigrams ===")

test("GET /rare-lemmata?language=la", lambda: (
    'total_rare_words' in check_json(requests.get(f"{BASE}/rare-lemmata?language=la&max_occurrences=3"))
))

test("GET /rare-bigrams?language=la", lambda: (
    requests.get(f"{BASE}/rare-bigrams?language=la&max_occurrences=10").status_code == 200
))


# ── Wildcard / String Search ───────────────────────────────────────

print("\n=== Wildcard Search ===")

test("POST /api/wildcard-search (arma vir*)", lambda: (
    check_json(requests.post(f"{BASE}/api/wildcard-search", json={
        "query": "arma vir*", "language": "la", "max_results": 10
    })).get('total_matches', 0) > 0
))


# ── Static Pages (HTML served) ────────────────────────────────────

print("\n=== Static Pages ===")

test("GET / (main page)", lambda: (
    requests.get(f"{BASE}/").status_code == 200
))

test("GET /help", lambda: (
    requests.get(f"{BASE}/help").status_code == 200
))

test("GET /about", lambda: (
    requests.get(f"{BASE}/about").status_code == 200
))


# ── Auth Status ────────────────────────────────────────────────────

print("\n=== Auth ===")

test("GET /api/auth/user", lambda: (
    requests.get(f"{BASE}/api/auth/user").status_code == 200
))


# ── Summary ─────────────────────────────────────────────────────────

print(f"\n{'='*50}")
print(f"Results: {PASS} passed, {FAIL} failed out of {PASS+FAIL} tests")
if ERRORS:
    print(f"\nFailed tests:")
    for e in ERRORS:
        print(f"  - {e}")
print(f"{'='*50}")

sys.exit(1 if FAIL > 0 else 0)
