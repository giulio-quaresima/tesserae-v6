"""
Tesserae V6 - Search Blueprint

This module handles the core intertextual search functionality, finding parallel
passages between a source text and a target text using various matching algorithms.

Key Features:
    - Streaming search with real-time progress updates (SSE)
    - Multiple match types: lemma, exact, sound, edit distance, semantic
    - Cross-lingual matching (Latin-Greek)
    - Configurable stoplist generation (Zipf-based)
    - V3-style scoring with IDF and distance metrics
    - Result caching for performance

Search Flow:
    1. Validate source/target texts exist
    2. Check cache for previous results
    3. Process texts into units (lines or phrases)
    4. Generate stoplists based on frequency
    5. Find matching lemmas/words between texts
    6. Score matches using V3 algorithm
    7. Filter and sort results
    8. Return formatted results with highlighting
"""

# =============================================================================
# IMPORTS
# =============================================================================
from flask import Blueprint, jsonify, request, Response
from flask_login import current_user
import os
import json
import time

from backend.logging_config import get_logger
from backend.services import get_user_location, log_search
from backend.cache import get_cached_results, save_cached_results, clear_cache

logger = get_logger('search')


# =============================================================================
# BLUEPRINT SETUP
# =============================================================================
search_bp = Blueprint('search', __name__)

# Module-level references to shared components (injected via init_search_blueprint)
_matcher = None       # Matcher: Finds parallel passages between texts
_scorer = None        # Scorer: Calculates V3-style similarity scores
_text_processor = None # TextProcessor: Tokenization and lemmatization
_texts_dir = None     # Path to corpus directory
_get_processed_units = None      # Function to get cached/processed text units
_get_corpus_frequencies = None   # Function to get word frequency data


def init_search_blueprint(matcher, scorer, text_processor, texts_dir, 
                          get_processed_units_fn, get_corpus_frequencies_fn):
    """
    Initialize blueprint with required dependencies.
    
    Called from app.py during startup to inject shared components.
    This pattern avoids circular imports while sharing state.
    """
    global _matcher, _scorer, _text_processor, _texts_dir
    global _get_processed_units, _get_corpus_frequencies
    _matcher = matcher
    _scorer = scorer
    _text_processor = text_processor
    _texts_dir = texts_dir
    _get_processed_units = get_processed_units_fn
    _get_corpus_frequencies = get_corpus_frequencies_fn


# =============================================================================
# SHARED SEARCH HELPERS
# =============================================================================

def _parse_search_request(data):
    """Parse and validate a search request from either endpoint.

    Returns dict with source_id, target_id, language, source_language,
    target_language, settings, source_path, target_path, is_crosslingual.
    Raises ValueError for missing fields, FileNotFoundError for missing texts.
    """
    source_id = data.get('source')
    target_id = data.get('target')
    language = data.get('language', 'la')
    source_language = data.get('source_language', language)
    target_language = data.get('target_language', language)

    settings = data.get('settings', {})
    for key in ['match_type', 'min_matches', 'max_results', 'max_distance',
                'stoplist_basis', 'stoplist_size', 'source_unit_type', 'target_unit_type',
                'use_meter', 'use_pos', 'use_syntax', 'use_sound', 'use_edit_distance',
                'bigram_boost', 'custom_stopwords']:
        if key in data and key not in settings:
            settings[key] = data[key]

    if not source_id or not target_id:
        raise ValueError('Please select both source and target texts')

    match_type = settings.get('match_type', 'lemma')
    is_crosslingual = match_type in ('semantic_cross', 'dictionary_cross', 'crosslingual_fusion')

    if is_crosslingual:
        source_path = os.path.join(_texts_dir, source_language, source_id)
        target_path = os.path.join(_texts_dir, target_language, target_id)
    else:
        lang_dir = os.path.join(_texts_dir, language)
        source_path = os.path.join(lang_dir, source_id)
        target_path = os.path.join(lang_dir, target_id)

    if not os.path.exists(source_path) or not os.path.exists(target_path):
        raise FileNotFoundError('Text files not found')

    settings['language'] = language
    settings['source_language'] = source_language
    settings['target_language'] = target_language
    settings['source_text_path'] = source_path
    settings['target_text_path'] = target_path

    return {
        'source_id': source_id, 'target_id': target_id,
        'language': language, 'source_language': source_language,
        'target_language': target_language, 'settings': settings,
        'source_path': source_path, 'target_path': target_path,
        'is_crosslingual': is_crosslingual,
    }


def _load_units(params):
    """Load processed text units for source and target texts."""
    settings = params['settings']
    source_unit_type = settings.get('source_unit_type', 'line')
    target_unit_type = settings.get('target_unit_type', 'line')

    if params['is_crosslingual']:
        source_units = _get_processed_units(params['source_id'], params['source_language'], source_unit_type, _text_processor)
        target_units = _get_processed_units(params['target_id'], params['target_language'], target_unit_type, _text_processor)
    else:
        source_units = _get_processed_units(params['source_id'], params['language'], source_unit_type, _text_processor)
        target_units = _get_processed_units(params['target_id'], params['language'], target_unit_type, _text_processor)

    return source_units, target_units


def _load_corpus_frequencies(language, settings):
    """Load corpus frequencies if stoplist basis requires them."""
    stoplist_basis = settings.get('stoplist_basis', 'source_target')
    if stoplist_basis == 'corpus':
        freq_data = _get_corpus_frequencies(language, _text_processor)
        if freq_data:
            return freq_data.get('frequencies', {})
    return None


def _run_matcher(match_type, source_units, target_units, settings, corpus_frequencies=None):
    """Dispatch to the appropriate matcher based on match_type.

    Returns (matches, stoplist_size).
    Raises ValueError for cross-lingual types that need special handling.
    """
    if match_type == 'sound':
        return _matcher.find_sound_matches(source_units, target_units, settings)
    elif match_type == 'edit_distance':
        return _matcher.find_edit_distance_matches(source_units, target_units, settings)
    elif match_type == 'semantic':
        from backend.semantic_similarity import find_semantic_matches
        return find_semantic_matches(source_units, target_units, settings)
    elif match_type == 'dictionary':
        from backend.semantic_similarity import find_dictionary_matches
        return find_dictionary_matches(source_units, target_units, settings)
    elif match_type in ('semantic_cross', 'dictionary_cross', 'crosslingual_fusion'):
        raise ValueError(f'Cross-lingual match type {match_type} requires special handling')
    else:
        return _matcher.find_matches(source_units, target_units, settings, corpus_frequencies)


def _finalize_results(scored_results, source_units, target_units, stoplist_size,
                      settings, source_id, target_id, language, cached=False):
    """Cache results, log the search, and build the response dict."""
    if not cached:
        metadata = {
            'source_lines': len(source_units),
            'target_lines': len(target_units),
            'stoplist_size': stoplist_size,
        }
        save_cached_results(source_id, target_id, language, settings, scored_results, metadata)

    max_results = settings.get('max_results', 0)
    display_results = scored_results[:max_results] if max_results > 0 else scored_results

    user_id = current_user.id if current_user and current_user.is_authenticated else None
    city, country = get_user_location()
    log_search('text_comparison', language, source_id, target_id, None,
               settings.get('match_type', 'lemma'), len(scored_results), cached, user_id,
               city, country)

    return {
        "results": display_results,
        "total_matches": len(scored_results),
        "source_lines": len(source_units),
        "target_lines": len(target_units),
        "stoplist_size": stoplist_size,
        "cached": cached,
    }


def _handle_dictionary_cross(params, source_units, target_units, settings):
    """Handle dictionary_cross match type with custom IDF-based result building.

    Unlike other match types, dictionary_cross builds results directly from
    matches (already sorted by IDF score) rather than going through the scorer.
    """
    from backend.semantic_similarity import find_dictionary_crosslingual_matches

    source_id = params['source_id']
    target_id = params['target_id']
    language = params['language']

    greek_freq_data = _get_corpus_frequencies('grc', _text_processor)
    latin_freq_data = _get_corpus_frequencies('la', _text_processor)
    greek_frequencies = greek_freq_data.get('frequencies', {}) if greek_freq_data else {}
    latin_frequencies = latin_freq_data.get('frequencies', {}) if latin_freq_data else {}

    matches, stoplist_size = find_dictionary_crosslingual_matches(
        source_units, target_units, params['source_language'],
        params['target_language'], settings,
        greek_frequencies=greek_frequencies, latin_frequencies=latin_frequencies
    )

    scored_results = []
    for m in matches:
        src_unit = source_units[m['source_idx']]
        tgt_unit = target_units[m['target_idx']]
        src_tokens = src_unit.get('tokens', [])
        tgt_tokens = tgt_unit.get('tokens', [])
        src_original = src_unit.get('original_tokens', src_tokens)
        tgt_original = tgt_unit.get('original_tokens', tgt_tokens)

        matched_words_with_original = []
        for wm in m.get('word_matches', []):
            grc_indices = wm.get('greek_indices', [])
            lat_indices = wm.get('latin_indices', [])
            grc_original = (src_original[grc_indices[0]]
                            if grc_indices and grc_indices[0] < len(src_original)
                            else wm['greek_lemma'])
            lat_original_word = (tgt_original[lat_indices[0]]
                                 if lat_indices and lat_indices[0] < len(tgt_original)
                                 else wm['latin_lemma'])
            matched_words_with_original.append({
                'greek_word': grc_original,
                'latin_word': lat_original_word,
                'greek_lemma': wm.get('greek_lemma', ''),
                'latin_lemma': wm.get('latin_lemma', ''),
                'display': f"{grc_original}\u2192{lat_original_word}",
                'type': 'cross_lingual',
                'idf': wm.get('idf_score', 0)
            })

        scored_results.append({
            'source': {
                'ref': src_unit.get('ref', ''),
                'text': src_unit.get('text', ''),
                'tokens': src_original,
                'highlight_indices': [idx for wm in m.get('word_matches', [])
                                      for idx in wm.get('greek_indices', [])]
            },
            'target': {
                'ref': tgt_unit.get('ref', ''),
                'text': tgt_unit.get('text', ''),
                'tokens': tgt_original,
                'highlight_indices': [idx for wm in m.get('word_matches', [])
                                      for idx in wm.get('latin_indices', [])]
            },
            'matched_words': matched_words_with_original,
            'match_count': m.get('match_count', 0),
            'distance': m.get('distance', 0),
            'idf_score': m.get('idf_score', 0),
            'overall_score': m.get('overall_score', 0),
            'match_basis': 'dictionary_cross'
        })

    return jsonify(_finalize_results(scored_results, source_units, target_units,
                                      stoplist_size, settings, source_id, target_id, language))


def _find_dictionary_matches_fast(source_units, target_units, source_language, target_language):
    """Fast inverted-index dictionary matching for cross-lingual fusion.

    Instead of O(n*m) calls to find_greek_latin_matches, builds an inverted
    index of target lemmas, then for each source lemma looks up translations
    and finds which target lines contain them.  Returns dict keyed by
    (src_idx, tgt_idx) with word_matches list.
    """
    import unicodedata
    from backend.synonym_dict import get_greek_latin_dict, CURATED_GREEK_LATIN, \
        CROSSLINGUAL_STOPLIST_GREEK, CROSSLINGUAL_STOPLIST_LATIN

    _, gl_dict_norm = get_greek_latin_dict()

    def strip_accents(s):
        nfd = unicodedata.normalize('NFD', s.lower())
        return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')

    # Determine which side is Greek, which is Latin
    if source_language == 'grc' and target_language == 'la':
        grc_units, lat_units = source_units, target_units
        grc_is_source = True
    else:
        grc_units, lat_units = target_units, source_units
        grc_is_source = False

    # Build inverted index: latin_lemma_norm -> set of (unit_idx, token_position)
    lat_lemma_index = {}
    for tgt_idx, unit in enumerate(lat_units):
        for pos, lemma in enumerate(unit.get('lemmas', [])):
            ln = lemma.lower()
            if ln in CROSSLINGUAL_STOPLIST_LATIN:
                continue
            lat_lemma_index.setdefault(ln, []).append((tgt_idx, pos))

    # For each Greek unit, look up translations and find target hits
    pair_matches = {}  # (src_idx, tgt_idx) -> list of word match dicts

    for grc_idx, grc_unit in enumerate(grc_units):
        grc_lemmas = grc_unit.get('lemmas', [])
        for grc_pos, grc_lemma in enumerate(grc_lemmas):
            grc_norm = strip_accents(grc_lemma)
            if grc_norm in CROSSLINGUAL_STOPLIST_GREEK:
                continue

            # Get all Latin translations for this Greek lemma
            translations = set()
            curated = CURATED_GREEK_LATIN.get(grc_norm, [])
            if curated:
                translations.update(w.lower() for w in curated)
            dict_trans = gl_dict_norm.get(grc_norm, set()) if gl_dict_norm else set()
            if dict_trans:
                translations.update(w.lower() for w in dict_trans)

            if not translations:
                continue

            # Look up which target lines contain these translations
            for lat_lemma in translations:
                if lat_lemma in CROSSLINGUAL_STOPLIST_LATIN:
                    continue
                hits = lat_lemma_index.get(lat_lemma)
                if not hits:
                    continue
                for lat_idx, lat_pos in hits:
                    if grc_is_source:
                        key = (grc_idx, lat_idx)
                    else:
                        key = (lat_idx, grc_idx)

                    wm = {
                        'greek_lemma': grc_norm,
                        'latin_lemma': lat_lemma,
                        'greek_indices': [grc_pos],
                        'latin_indices': [lat_pos],
                    }
                    pair_matches.setdefault(key, []).append(wm)

    # Deduplicate: collapse multiple hits of same lemma pair per line pair
    for key in pair_matches:
        seen = {}
        deduped = []
        for wm in pair_matches[key]:
            pair_key = (wm['greek_lemma'], wm['latin_lemma'])
            if pair_key not in seen:
                seen[pair_key] = wm
                deduped.append(wm)
            else:
                # Merge indices
                existing = seen[pair_key]
                for gi in wm['greek_indices']:
                    if gi not in existing['greek_indices']:
                        existing['greek_indices'].append(gi)
                for li in wm['latin_indices']:
                    if li not in existing['latin_indices']:
                        existing['latin_indices'].append(li)
        pair_matches[key] = deduped

    return pair_matches


def _handle_crosslingual_fusion(params, source_units, target_units, settings):
    """Two-channel cross-lingual fusion: semantic (SPhilBERTa) + dictionary.

    Runs both channels, merges by (source_idx, target_idx), and applies a
    convergence bonus when both channels fire on the same pair.
    """
    import math
    from backend.semantic_similarity import find_crosslingual_matches
    from backend.synonym_dict import find_greek_latin_matches

    source_id = params['source_id']
    target_id = params['target_id']
    language = params['language']
    min_matches = settings.get('min_matches', 1)

    # --- Channel 1: Semantic (SPhilBERTa cosine) ---
    sem_settings = {**settings, 'max_results': 2000, 'semantic_top_n': 20}
    sem_matches, _ = find_crosslingual_matches(
        source_units, target_units,
        params['source_language'], params['target_language'], sem_settings)

    # Index semantic results by pair key
    sem_by_pair = {}
    for m in sem_matches:
        key = (m['source_idx'], m['target_idx'])
        sem_by_pair[key] = m.get('semantic_score', 0.0)

    # --- Channel 2: Dictionary (fast inverted-index lookup) ---
    print("Running fast dictionary matching...")
    dict_by_pair = _find_dictionary_matches_fast(
        source_units, target_units,
        params['source_language'], params['target_language'])
    print(f"Dictionary found {len(dict_by_pair)} pairs with matches")

    # --- Semantic recovery for dictionary-only pairs ---
    # Dictionary pairs not found by the semantic channel (filtered by top-N cap)
    # get their actual cosine looked up from pre-computed embeddings.
    dict_only_keys = set(dict_by_pair.keys()) - set(sem_by_pair.keys())
    if dict_only_keys:
        try:
            from backend.embedding_storage import load_embeddings
            import numpy as np
            src_path = settings.get('source_text_path')
            tgt_path = settings.get('target_text_path')
            src_emb = load_embeddings(src_path, params['source_language']) if src_path else None
            tgt_emb = load_embeddings(tgt_path, params['target_language']) if tgt_path else None
            if src_emb is not None and tgt_emb is not None:
                src_emb = src_emb[:len(source_units)]
                tgt_emb = tgt_emb[:len(target_units)]
                # Normalise
                src_norms = np.linalg.norm(src_emb, axis=1, keepdims=True)
                tgt_norms = np.linalg.norm(tgt_emb, axis=1, keepdims=True)
                src_emb = src_emb / (src_norms + 1e-8)
                tgt_emb = tgt_emb / (tgt_norms + 1e-8)
                recovered = 0
                for key in dict_only_keys:
                    si, ti = key
                    if si < len(src_emb) and ti < len(tgt_emb):
                        cosine = float(np.dot(src_emb[si], tgt_emb[ti]))
                        if cosine > 0.4:
                            sem_by_pair[key] = cosine
                            recovered += 1
                print(f"Semantic recovery: {recovered}/{len(dict_only_keys)} dictionary-only pairs got cosine scores")
        except Exception as e:
            print(f"Semantic recovery failed: {e}")

    # --- Local IDF from source+target texts (avoids slow corpus freq lookup) ---
    import unicodedata
    def strip_accents(s):
        nfd = unicodedata.normalize('NFD', s.lower())
        return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')

    # Count document frequency: how many lines contain each lemma
    doc_freq = {}
    for unit in source_units:
        seen = set()
        for lemma in unit.get('lemmas', []):
            norm = strip_accents(lemma)
            if norm not in seen:
                doc_freq[norm] = doc_freq.get(norm, 0) + 1
                seen.add(norm)
    for unit in target_units:
        seen = set()
        for lemma in unit.get('lemmas', []):
            norm = lemma.lower()
            if norm not in seen:
                doc_freq[norm] = doc_freq.get(norm, 0) + 1
                seen.add(norm)
    total_docs = len(source_units) + len(target_units)

    def calc_idf(lemma, is_greek=False):
        key = strip_accents(lemma) if is_greek else lemma.lower()
        df = doc_freq.get(key, 1)
        return math.log((total_docs + 1) / (df + 1)) + 1

    # --- Merge ---
    all_keys = set(sem_by_pair.keys()) | set(dict_by_pair.keys())

    SEMANTIC_WEIGHT = 1.2
    DICTIONARY_WEIGHT = 2.0
    CONVERGENCE_BONUS = 0.5  # additive bonus when both channels fire

    fused = []
    for key in all_keys:
        src_idx, tgt_idx = key
        cosine = sem_by_pair.get(key, 0.0)
        dict_wms = dict_by_pair.get(key)  # list of word match dicts or None

        has_semantic = cosine > 0
        has_dict = dict_wms is not None

        # Count unique words per side for dict matches
        dict_word_count = 0
        avg_idf = 0.0
        if has_dict:
            unique_grc = set(wm['greek_lemma'] for wm in dict_wms)
            unique_lat = set(wm['latin_lemma'] for wm in dict_wms)
            dict_word_count = min(len(unique_grc), len(unique_lat))

            # Compute average IDF
            total_idf = 0.0
            for wm in dict_wms:
                gi = calc_idf(wm['greek_lemma'], is_greek=True)
                li = calc_idf(wm['latin_lemma'], is_greek=False)
                wm['idf_score'] = (gi + li) / 2
                total_idf += wm['idf_score']
            avg_idf = total_idf / len(dict_wms) if dict_wms else 0

        # Dictionary score: avg_idf scaled by match count (multiple rare matches >> 1 common)
        dict_score = (min(avg_idf / 10.0, 1.0) * math.sqrt(dict_word_count)) if has_dict else 0.0

        # Apply min_matches filter to dictionary side
        if has_dict and dict_word_count < min_matches:
            has_dict = False
            dict_score = 0.0
            dict_word_count = 0
            dict_wms = None

        # Skip pairs with neither channel
        if not has_semantic and not has_dict:
            continue

        # Fused score (additive, matching article formula)
        score = (cosine * SEMANTIC_WEIGHT) + (dict_score * DICTIONARY_WEIGHT)
        n_channels = (1 if has_semantic else 0) + (1 if has_dict else 0)
        if n_channels == 2:
            score += CONVERGENCE_BONUS

        # Build result
        src_unit = source_units[src_idx]
        tgt_unit = target_units[tgt_idx]
        src_tokens = src_unit.get('tokens', [])
        tgt_tokens = tgt_unit.get('tokens', [])
        src_original = src_unit.get('original_tokens', src_tokens)
        tgt_original = tgt_unit.get('original_tokens', tgt_tokens)

        # Get word-level matches for highlighting
        matched_words = []
        source_highlights = []
        target_highlights = []

        if has_dict:
            for wm in dict_wms:
                grc_indices = wm.get('greek_indices', [])
                lat_indices = wm.get('latin_indices', [])
                # Determine which side is source vs target
                if params['source_language'] == 'grc':
                    s_indices, t_indices = grc_indices, lat_indices
                else:
                    s_indices, t_indices = lat_indices, grc_indices
                grc_word = (src_original[s_indices[0]]
                            if s_indices and s_indices[0] < len(src_original)
                            else wm['greek_lemma'])
                lat_word = (tgt_original[t_indices[0]]
                            if t_indices and t_indices[0] < len(tgt_original)
                            else wm['latin_lemma'])
                matched_words.append({
                    'greek_word': grc_word,
                    'latin_word': lat_word,
                    'greek_lemma': wm.get('greek_lemma', ''),
                    'latin_lemma': wm.get('latin_lemma', ''),
                    'display': f"{grc_word}\u2192{lat_word}",
                    'type': 'cross_lingual',
                    'idf': wm.get('idf_score', 0)
                })
                source_highlights.extend(s_indices)
                target_highlights.extend(t_indices)
        elif has_semantic:
            # Semantic-only: try dictionary lookup for highlights
            src_lemmas = src_unit.get('lemmas', [])
            tgt_lemmas = tgt_unit.get('lemmas', [])
            try:
                if params['source_language'] == 'grc':
                    gl = find_greek_latin_matches(src_lemmas, tgt_lemmas)
                else:
                    gl = find_greek_latin_matches(tgt_lemmas, src_lemmas)
                    for g in gl:
                        g['greek_indices'], g['latin_indices'] = g['latin_indices'], g['greek_indices']
                for g in gl:
                    if params['source_language'] == 'grc':
                        s_idx_list, t_idx_list = g.get('greek_indices', []), g.get('latin_indices', [])
                    else:
                        s_idx_list, t_idx_list = g.get('latin_indices', []), g.get('greek_indices', [])
                    source_highlights.extend(s_idx_list)
                    target_highlights.extend(t_idx_list)
                    grc_w = src_tokens[s_idx_list[0]] if s_idx_list and s_idx_list[0] < len(src_tokens) else g['greek_lemma']
                    lat_w = tgt_tokens[t_idx_list[0]] if t_idx_list and t_idx_list[0] < len(tgt_tokens) else g['latin_lemma']
                    matched_words.append({
                        'greek_word': grc_w, 'latin_word': lat_w,
                        'greek_lemma': g['greek_lemma'], 'latin_lemma': g['latin_lemma'],
                        'display': f"{grc_w}\u2192{lat_w}",
                        'type': 'cross_lingual'
                    })
            except Exception:
                pass

        if not matched_words:
            matched_words = [{
                'type': 'semantic_cross',
                'similarity': cosine,
                'display': f'Semantic similarity ({int(cosine*100)}%)',
                'lemma': 'semantic_cross'
            }]

        channels = []
        if has_semantic:
            channels.append(f'semantic ({int(cosine*100)}%)')
        if has_dict:
            channels.append(f'dictionary ({dict_word_count} words)')

        fused.append({
            'source': {
                'ref': src_unit.get('ref', ''),
                'text': src_unit.get('text', ''),
                'tokens': src_original,
                'highlight_indices': sorted(set(source_highlights))
            },
            'target': {
                'ref': tgt_unit.get('ref', ''),
                'text': tgt_unit.get('text', ''),
                'tokens': tgt_original,
                'highlight_indices': sorted(set(target_highlights))
            },
            'matched_words': matched_words,
            'match_count': dict_word_count,
            'overall_score': score,
            'features': {
                'semantic_score': cosine,
                'dict_score': dict_score,
                'n_channels': n_channels,
            },
            'channels': ', '.join(channels),
            'match_basis': 'crosslingual_fusion'
        })

    fused.sort(key=lambda x: x['overall_score'], reverse=True)

    max_results = settings.get('max_results', 500)
    if max_results > 0:
        fused = fused[:max_results]

    print(f"Cross-lingual fusion: {len(fused)} results "
          f"({len(sem_by_pair)} semantic, {len(dict_by_pair)} dictionary, "
          f"{len(set(sem_by_pair) & set(dict_by_pair))} overlap)")

    return jsonify(_finalize_results(fused, source_units, target_units,
                                      0, settings, source_id, target_id, language))


# =============================================================================
# STREAMING SEARCH ENDPOINT
# =============================================================================

@search_bp.route('/search-stream', methods=['POST'])
def search_stream():
    """Main text comparison search with SSE progress streaming."""
    data = request.get_json()

    def generate():
        try:
            start_time = time.time()

            def send_progress(step, detail=""):
                elapsed = round(time.time() - start_time, 1)
                msg = {"type": "progress", "step": step, "detail": detail, "elapsed": elapsed}
                return f"data: {json.dumps(msg)}\n\n"

            yield send_progress("Initializing search")

            try:
                params = _parse_search_request(data)
            except (ValueError, FileNotFoundError) as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                return

            settings = params['settings']
            source_id = params['source_id']
            target_id = params['target_id']
            language = params['language']
            match_type = settings.get('match_type', 'lemma')

            # Check cache
            cached_results, cached_meta = get_cached_results(source_id, target_id, language, settings)
            if cached_results is not None:
                yield send_progress("Loading cached results")
                max_results = settings.get('max_results', 0)
                display_results = cached_results[:max_results] if max_results > 0 else cached_results
                meta = cached_meta or {}
                result = {
                    "type": "complete",
                    "results": display_results,
                    "total_matches": len(cached_results),
                    "source_lines": meta.get('source_lines', 0),
                    "target_lines": meta.get('target_lines', 0),
                    "stoplist_size": meta.get('stoplist_size', 0),
                    "elapsed_time": round(time.time() - start_time, 2),
                    "cached": True
                }
                yield f"data: {json.dumps(result)}\n\n"
                return

            # Load text units (with per-text progress messages)
            source_unit_type = settings.get('source_unit_type', 'line')
            target_unit_type = settings.get('target_unit_type', 'line')

            yield send_progress("Loading source text", source_id.replace('.tess', ''))
            if params['is_crosslingual']:
                source_units = _get_processed_units(source_id, params['source_language'], source_unit_type, _text_processor)
            else:
                source_units = _get_processed_units(source_id, language, source_unit_type, _text_processor)

            yield send_progress("Loading target text", target_id.replace('.tess', ''))
            if params['is_crosslingual']:
                target_units = _get_processed_units(target_id, params['target_language'], target_unit_type, _text_processor)
            else:
                target_units = _get_processed_units(target_id, language, target_unit_type, _text_processor)

            # Load corpus frequencies if needed
            if settings.get('stoplist_basis', 'source_target') == 'corpus':
                yield send_progress("Loading corpus frequencies")
            corpus_frequencies = _load_corpus_frequencies(language, settings)

            # Find matches
            yield send_progress("Finding matches", f"{len(source_units)} \u00d7 {len(target_units)} units")
            try:
                matches, stoplist_size = _run_matcher(match_type, source_units, target_units, settings, corpus_frequencies)
            except ValueError:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Use regular search endpoint for cross-lingual'})}\n\n"
                return

            if not matches:
                result = {
                    "type": "complete",
                    "results": [],
                    "total_matches": 0,
                    "source_lines": len(source_units),
                    "target_lines": len(target_units),
                    "stoplist_size": stoplist_size,
                    "elapsed_time": round(time.time() - start_time, 2)
                }
                yield f"data: {json.dumps(result)}\n\n"
                return

            # Score, cache, log, and return
            yield send_progress("Scoring matches", f"{len(matches)} candidates")
            scored_results = _scorer.score_matches(matches, source_units, target_units, settings, source_id, target_id)
            scored_results.sort(key=lambda x: x['overall_score'], reverse=True)

            yield send_progress("Saving to cache")
            response_data = _finalize_results(scored_results, source_units, target_units,
                                               stoplist_size, settings, source_id, target_id, language)

            elapsed_time = round(time.time() - start_time, 2)
            result = {
                "type": "complete",
                "results": response_data["results"],
                "total_matches": response_data["total_matches"],
                "source_lines": response_data["source_lines"],
                "target_lines": response_data["target_lines"],
                "stoplist_size": response_data["stoplist_size"],
                "elapsed_time": elapsed_time
            }
            yield f"data: {json.dumps(result)}\n\n"

        except Exception as e:
            logger.error(f"Search stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    })


@search_bp.route('/search', methods=['POST'])
def search():
    """Non-streaming text comparison search (POST /api/search).

    Matches source vs target text using the specified match_type (lemma, exact, sound,
    edit_distance, semantic, dictionary, or cross-lingual variants). Returns all results
    at once with matched_words, scores, and highlight indices.
    """
    try:
        data = request.get_json()
        params = _parse_search_request(data)
        settings = params['settings']
        source_id = params['source_id']
        target_id = params['target_id']
        language = params['language']
        match_type = settings.get('match_type', 'lemma')

        # Check cache
        cached_results, cached_meta = get_cached_results(source_id, target_id, language, settings)
        if cached_results is not None:
            max_results = settings.get('max_results', 0)
            display_results = cached_results[:max_results] if max_results > 0 else cached_results
            user_id = current_user.id if current_user and current_user.is_authenticated else None
            city, country = get_user_location()
            log_search('text_comparison', language, source_id, target_id, None,
                      match_type, len(cached_results), True, user_id, city, country)
            meta = cached_meta or {}
            return jsonify({
                "results": display_results,
                "total_matches": len(cached_results),
                "source_lines": meta.get('source_lines', 0),
                "target_lines": meta.get('target_lines', 0),
                "stoplist_size": meta.get('stoplist_size', 0),
                "cached": True
            })

        # Load text units and corpus frequencies
        source_units, target_units = _load_units(params)
        corpus_frequencies = _load_corpus_frequencies(language, settings)

        # Cross-lingual fusion (default for cross-lingual searches)
        if match_type == 'crosslingual_fusion':
            return _handle_crosslingual_fusion(params, source_units, target_units, settings)

        # Legacy single-channel cross-lingual paths
        if match_type == 'dictionary_cross':
            return _handle_dictionary_cross(params, source_units, target_units, settings)
        if match_type == 'semantic_cross':
            from backend.semantic_similarity import find_crosslingual_matches
            matches, stoplist_size = find_crosslingual_matches(
                source_units, target_units, params['source_language'],
                params['target_language'], settings)
        else:
            matches, stoplist_size = _run_matcher(match_type, source_units, target_units,
                                                   settings, corpus_frequencies)

        # Score, cache, log, and return
        scored_results = _scorer.score_matches(matches, source_units, target_units, settings, source_id, target_id)
        scored_results.sort(key=lambda x: x['overall_score'], reverse=True)
        return jsonify(_finalize_results(scored_results, source_units, target_units,
                                          stoplist_size, settings, source_id, target_id, language))

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)})


@search_bp.route('/stoplist', methods=['POST'])
def get_stoplist():
    """Get the computed stoplist for given texts and settings"""
    data = request.get_json() or {}
    source_id = data.get('source', '')
    target_id = data.get('target', '')
    language = data.get('language', 'la')
    stoplist_basis = data.get('stoplist_basis', 'source_target')
    stoplist_size = data.get('stoplist_size', 0)
    
    if stoplist_size == -1:
        return jsonify({'stopwords': [], 'count': 0})
    
    try:
        source_units = _get_processed_units(source_id, language, 'line', _text_processor)
        target_units = _get_processed_units(target_id, language, 'line', _text_processor)
        
        corpus_frequencies = None
        if stoplist_basis == 'corpus':
            freq_data = _get_corpus_frequencies(language, _text_processor)
            if freq_data:
                corpus_frequencies = freq_data.get('frequencies', {})
        
        if stoplist_size > 0:
            stopwords = _matcher.build_stoplist_manual(source_units + target_units, stoplist_size, language)
        else:
            stopwords = _matcher.build_stoplist(source_units, target_units, stoplist_basis, language, corpus_frequencies)
        
        return jsonify({
            'stopwords': sorted(list(stopwords)),
            'count': len(stopwords)
        })
    except Exception as e:
        return jsonify({'error': str(e), 'stopwords': []})


@search_bp.route('/cache/clear', methods=['POST'])
def clear_search_cache():
    """Clear all cached search results - available to all users"""
    try:
        count = clear_cache()
        logger.info(f"Search cache cleared: {count} cached searches removed")
        return jsonify({
            'success': True,
            'message': f'Cleared {count} cached searches',
            'count': count
        })
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@search_bp.route('/wildcard-search', methods=['POST'])
def wildcard_search_endpoint():
    """
    PHI-style wildcard/boolean search.
    
    Supports:
    - Wildcards: am* (starts with), *or (ends with), ?or (single char)
    - Boolean: amor AND dolor, virtus OR honos, amor NOT bellum
    - Phrases: "arma virumque"
    """
    try:
        from backend.wildcard_search import wildcard_search
        
        data = request.get_json()
        query = data.get('query', '').strip()
        language = data.get('language', 'la')
        target_text = data.get('target_text')
        case_sensitive = data.get('case_sensitive', False)
        max_results = data.get('max_results', 500)
        era_filter = data.get('era_filter')
        
        if not query:
            return jsonify({'error': 'Query is required', 'results': []})
        
        results = wildcard_search(
            language=language,
            query=query,
            target_text=target_text,
            case_sensitive=case_sensitive,
            max_results=max_results,
            era_filter=era_filter
        )
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Wildcard search error: {e}")
        return jsonify({'error': str(e), 'results': []}), 500
