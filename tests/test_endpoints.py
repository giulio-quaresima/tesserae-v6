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

test("GET /api/rare-lemmata?language=la", lambda: (
    'total_rare_words' in check_json(requests.get(f"{BASE}/api/rare-lemmata?language=la&max_occurrences=3"))
))

test("GET /api/rare-bigrams?language=la", lambda: (
    requests.get(f"{BASE}/api/rare-bigrams?language=la&max_occurrences=10").status_code == 200
))


# ── Wildcard / String Search ───────────────────────────────────────

print("\n=== Wildcard Search ===")

test("POST /api/wildcard-search (arma vir*)", lambda: (
    check_json(requests.post(f"{BASE}/api/wildcard-search", json={
        "query": "arma vir*", "language": "la", "max_results": 10
    })).get('total_matches', 0) > 0
))


# ── Result Quality Checks ─────────────────────────────────────────

print("\n=== Result Quality Checks ===")

def check_hapax_quality():
    """Hapax search must find truly rare words (by document frequency), not common ones."""
    data = requests.post(f"{BASE}/api/hapax-search", json={
        "source": "vergil.aeneid.tess",
        "target": "lucan.bellum_civile.tess",
        "language": "la",
        "max_occurrences": 5
    }, timeout=120).json()
    results = data.get('results', [])
    assert len(results) > 0, "No hapax results returned"
    lemmas = {r['lemma'] for r in results}
    # hadriacas appears in only 3 texts — must be found
    assert 'hadriacas' in lemmas, f"Missing known rare word 'hadriacas'; got: {sorted(lemmas)[:10]}"
    # Common words must NOT appear (aspero = 77 texts, foedo = 216 texts)
    for bad in ['aspero', 'foedo', 'foederis']:
        assert bad not in lemmas, f"Common word '{bad}' should not appear in hapax results"
    # corpus_count should reflect document frequency, not token frequency
    for r in results:
        assert r['corpus_count'] <= 5, f"Lemma '{r['lemma']}' has corpus_count={r['corpus_count']} > max_occurrences=5"
    return True

test("Hapax quality: Aen × BC has hadriacas, no common words", check_hapax_quality)

def check_lemma_search_reference():
    """Lemma search results must have scores, matched words, and source/target text."""
    last = test_sse_search("/api/search-stream", {
        "source": "vergil.aeneid.part.1.tess",
        "target": "lucan.bellum_civile.part.1.tess",
        "language": "la",
        "match_type": "lemma",
        "min_matches": 2,
        "stoplist_size": 10,
        "stoplist_basis": "corpus",
        "source_unit_type": "line",
        "target_unit_type": "line",
        "max_distance": 999,
        "max_results": 500
    })
    results = last.get('results', [])
    assert len(results) >= 10, f"Too few results: {len(results)}"
    r0 = results[0]
    for key in ['source', 'target', 'matched_words', 'overall_score']:
        assert key in r0, f"Missing key '{key}' in search result"
    assert r0['overall_score'] > 0, "Score should be positive"
    assert len(r0['matched_words']) > 0, "No matched words in top result"
    return True

test("Lemma search quality: results have scores and matched words", check_lemma_search_reference)

def check_line_search_quality():
    """Line search for 'arma virumque cano' must find Aeneid somewhere in results."""
    data = requests.post(f"{BASE}/api/line-search", json={
        "query": "arma virumque cano", "language": "la"
    }, timeout=30).json()
    results = data.get('results', [])
    assert len(results) > 0, "No line search results"
    # Aeneid must appear somewhere in the results (not necessarily top 3,
    # since prose lines with more word matches may rank higher)
    texts = [r.get('text_id', '') for r in results]
    found_aeneid = any('aeneid' in t.lower() for t in texts)
    assert found_aeneid, f"Aeneid not found in any of {len(results)} results"
    return True

test("Line search quality: 'arma virumque cano' finds Aeneid", check_line_search_quality)

def check_corpus_search_quality():
    """Corpus search for arma+uir must return multiple texts."""
    data = requests.post(f"{BASE}/api/corpus-search", json={
        "lemmas": ["arma", "uir"], "language": "la"
    }, timeout=30).json()
    total = data.get('total', 0)
    assert total >= 5, f"Expected 5+ texts with arma+uir, got {total}"
    results = data.get('results', [])
    if results:
        r0 = results[0]
        assert 'text_id' in r0, "Missing text_id in corpus search result"
    return True

test("Corpus search quality: arma+uir finds 5+ texts", check_corpus_search_quality)

def check_wildcard_quality():
    """Wildcard search for 'arma vir*' must find Aeneid."""
    data = requests.post(f"{BASE}/api/wildcard-search", json={
        "query": "arma vir*", "language": "la", "max_results": 50
    }, timeout=30).json()
    total = data.get('total_matches', 0)
    assert total > 0, "No wildcard matches"
    results = data.get('results', [])
    texts = [r.get('text_id', '') for r in results]
    found_aeneid = any('aeneid' in t.lower() for t in texts)
    assert found_aeneid, f"Aeneid not in wildcard results for 'arma vir*'"
    return True

test("Wildcard quality: 'arma vir*' finds Aeneid", check_wildcard_quality)

def check_rare_bigrams_loaded():
    """Rare bigrams endpoint must return actual bigrams, not an index-missing error."""
    data = requests.get(f"{BASE}/api/rare-bigrams?language=la&max_occurrences=10", timeout=30).json()
    bigrams = data.get('bigrams', [])
    assert len(bigrams) > 0, f"No bigrams returned; message: {data.get('message', '')}"
    # Verify bigram structure
    b0 = bigrams[0]
    assert 'bigram' in b0 or 'word1' in b0, f"Bigram missing expected keys: {list(b0.keys())}"
    return True

test("Rare bigrams: Latin index loaded with actual data", check_rare_bigrams_loaded)

def check_fusion_result_quality():
    """Fusion results must include scores and matched words."""
    last = test_sse_search("/api/search-fusion", {
        "source": "lucan.bellum_civile.part.1.tess",
        "target": "vergil.aeneid.part.1.tess",
        "language": "la",
        "mode": "merged",
        "max_results": 50,
        "source_unit_type": "line",
        "target_unit_type": "line",
        "use_meter": False
    })
    results = last.get('results', [])
    assert len(results) >= 10, f"Too few fusion results: {len(results)}"
    r0 = results[0]
    assert r0.get('overall_score', 0) > 0, "Top fusion result has no score"
    assert 'matched_words' in r0, "Fusion result missing matched_words"
    assert 'channels' in r0 or 'match_basis' in r0, "Fusion result missing channel info"
    return True

test("Fusion quality: results have scores, words, channels", check_fusion_result_quality)


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
