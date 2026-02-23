"""
Tesserae V6 — Fusion Search Engine

Implements multi-channel weighted score fusion with a two-pass
line/window architecture for intertext detection.

Architecture
------------
The search operates in two passes over each text pair:

  Pass 1 — Line-level: All channels run on individual verse lines.
      This is the primary search, providing full 9-channel coverage.

  Pass 2 — Window-level: A subset of channels run on sliding windows
      of 2 consecutive lines. This captures enjambed allusions — cases
      where the verbal echo spans a line break and is therefore split
      across two line-level units.

Channel taxonomy
----------------
Channels are classified by the *level of linguistic representation*
at which they operate, which determines their behavior under windowing:

  LEXICAL channels (lemma, exact, rare_word, lemma_min1) match on the
  identity of word forms or lemmata. A lexical match between line-pair
  (s_i, t_j) requires the matching tokens to co-occur in those specific
  units. When an allusion is enjambed, the matching tokens are split
  across s_i and s_{i+1}; the window pass recovers this by combining
  them into a single unit.

  SUB-LEXICAL channels (edit_distance, sound) match on character-level
  similarity (Levenshtein distance, trigram overlap). These operate on
  individual tokens: if token A in s_i is phonetically similar to token
  B in t_j, that relationship is captured in the line pass regardless
  of whether adjacent lines are also considered. Windowing does not
  create new sub-lexical relationships between tokens.

  DISTRIBUTIONAL channels (semantic) match on vector similarity
  (SPhilBERTa embeddings). These capture pairwise token relationships
  already fully enumerated in the line pass.

  DICTIONARY channel uses curated synonym pairs with min_matches=2
  co-occurrence threshold. Despite being distributional, the threshold
  requirement means it benefits from windowing the same way lexical
  channels do: two synonym pairs split across adjacent lines are
  recovered when combined into a window.

  STRUCTURAL channels (syntax) match on dependency-tree patterns
  from pre-parsed data in syntax_latin.db. These are line-level by
  nature (parsed per-line from UD treebanks).

Window-pass channel selection rationale
---------------------------------------
Four channels run on windows (lemma, lemma_min1, rare_word, dictionary):

  1. These channels require co-occurrence (2+ matches) within a single
     unit. Windowing genuinely expands the match space by combining
     tokens from adjacent lines into one unit.

  2. Exact is excluded despite being lexical: it duplicates lemma's
     window coverage while being the slowest window channel (30+ min
     on large pairs like Aeneid × Metamorphoses). Benchmark cost:
     1/862 gold pairs (0.1%).

  3. Sub-lexical channels (edit_distance, sound) and semantic measure
     pairwise similarity between individual tokens, already enumerated
     exhaustively in the line pass; windowing adds no new token pairs.

  4. Empirically, adding dictionary to windows recovered 12 gold finds
     across 5 benchmarks. Sound and edit_distance on windows produced
     only 14 additional sound matches and zero new edit_distance
     matches while consuming 84% of window-pass runtime.

Scoring
-------
Weighted score fusion with convergence bonus:
  fused_score = sum(channel_score_i * weight_i) + 0.5 * (N_channels - 1)

Channel weights are from Config D. Production fusion achieves 90.8%
recall across 5 benchmark pairs (783/862). See research/studies/.
"""

import json
import math
import os
import re
import sqlite3
from collections import defaultdict


# ---------------------------------------------------------------------------
# Config D channel weights (validated across 5 benchmark pairs, Feb 2026)
# Weights reflect each channel's independent contribution to recall,
# determined by ablation study. Higher weight = stronger signal.
# ---------------------------------------------------------------------------
CHANNEL_WEIGHTS = {
    "edit_distance": 4.0,   # sub-lexical: Levenshtein fuzzy match
    "sound": 3.0,           # sub-lexical: character trigram overlap
    "exact": 2.0,           # lexical: identical surface forms
    "lemma": 1.5,           # lexical: shared dictionary headwords
    "dictionary": 1.0,      # distributional: curated synonym pairs
    "semantic": 0.8,        # distributional: SPhilBERTa cosine sim
    "rare_word": 0.5,       # lexical: shared low-frequency lemmata
    "syntax": 0.5,          # structural: dependency pattern match
    "lemma_min1": 0.3,      # lexical: single shared lemma (high recall, low precision)
}

# Bonus added for each additional channel beyond the first that confirms
# a pair, rewarding cross-channel convergence as evidence of a true allusion.
CONVERGENCE_BONUS = 0.5

# ---------------------------------------------------------------------------
# Channel classification for two-pass architecture
# ---------------------------------------------------------------------------

# Lexical channels (require token co-occurrence in unit)
LEXICAL_CHANNELS = ["lemma", "lemma_min1", "exact", "rare_word"]

# Window pass: channels that benefit from 2-line sliding windows.
# Includes lexical channels (minus exact) plus dictionary.
# - Exact is excluded: it duplicates lemma's coverage on windows while being
#   the slowest window channel (character-level comparison on large pairs can
#   take 30+ minutes). Benchmark impact: 1/862 gold pairs lost (VF-Vergil).
# - Dictionary is included: its min_matches>=2 co-occurrence threshold gives
#   it the same sensitivity to unit boundaries as lexical channels.
WINDOW_CHANNELS = ["lemma", "lemma_min1", "rare_word", "dictionary"]

# Channels whose matching is exhaustive at line level (pairwise token similarity)
LINE_ONLY_CHANNELS = ["edit_distance", "sound", "semantic"]

# All channels run in the line pass
ALL_CHANNELS = list(CHANNEL_WEIGHTS.keys())

# Execution order: fast channels first for progressive streaming.
# Users see results within seconds (lemma completes in <1s) rather than
# waiting minutes for edit_distance/sound to finish.
CHANNEL_ORDER = [
    "lemma",         # fast, high quality — gives first results immediately
    "exact",         # fast, high precision
    "rare_word",     # fast, sparse
    "dictionary",    # fast-medium
    "syntax",        # fast, DB lookup
    "lemma_min1",    # fast, high-recall
    "semantic",      # slow (~2 min), I/O-bound
    "sound",         # slow (~3 min), CPU-bound multiprocessing
    "edit_distance",  # slowest (~3.5 min), CPU-bound multiprocessing
]

# Channel configurations (match the evaluation study)
CHANNEL_CONFIGS = {
    "lemma": {
        "match_type": "lemma",
        "min_matches": 2,
        "language": "la",
        "stoplist_basis": "source_target",
        "stoplist_size": -1,
        "unbounded_scoring": True,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "lemma_min1": {
        "match_type": "lemma",
        "min_matches": 1,
        "language": "la",
        "stoplist_basis": "source_target",
        "stoplist_size": -1,
        "unbounded_scoring": True,
        "max_results": 50000,  # cap: weight is only 0.3, diminishing returns beyond top 50K
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "exact": {
        "match_type": "exact",
        "min_matches": 2,
        "language": "la",
        "stoplist_basis": "source_target",
        "stoplist_size": -1,
        "unbounded_scoring": True,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "semantic": {
        "match_type": "semantic",
        "min_matches": 2,
        "language": "la",
        "unbounded_scoring": True,
        "min_semantic_matches": 0,
        "semantic_only_threshold": 0.85,
        "min_semantic_score": 0.5,
        "semantic_top_n": 100,
        "max_results": 50000,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "dictionary": {
        "match_type": "dictionary",
        "min_matches": 2,
        "language": "la",
        "include_lemma_matches": True,
        "unbounded_scoring": True,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "sound": {
        "match_type": "sound",
        "min_matches": 2,
        "language": "la",
        "unbounded_scoring": True,
        "max_results": 50000,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "edit_distance": {
        "match_type": "edit_distance",
        "min_matches": 2,
        "language": "la",
        "unbounded_scoring": True,
        "edit_include_exact": True,
        "edit_min_shared_trigrams": 1,
        "min_edit_similarity": 0.6,
        "edit_top_n": 100,
        "max_results": 50000,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "syntax": {
        "match_type": "syntax",
    },
    "rare_word": {
        "match_type": "rare_word",
        "min_matches": 2,
        "language": "la",
        "unbounded_scoring": True,
        "rare_word_max_occurrences": 50,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
}


def make_window_units(line_units):
    """Create 2-line sliding window units from line units.

    Each window combines consecutive lines into a single unit with
    combined text, tokens, lemmas, and a range ref like 'luc. 1.1-luc. 1.2'.
    """
    windows = []
    for i in range(len(line_units) - 1):
        u1 = line_units[i]
        u2 = line_units[i + 1]
        window = {
            'ref': f"{u1['ref']}-{u2['ref']}",
            'text': u1['text'] + ' ' + u2['text'],
            'tokens': u1['tokens'] + u2['tokens'],
            'original_tokens': (
                u1.get('original_tokens', u1['tokens'])
                + u2.get('original_tokens', u2['tokens'])
            ),
            'lemmas': u1['lemmas'] + u2['lemmas'],
            'pos_tags': u1.get('pos_tags', []) + u2.get('pos_tags', []),
            'line_refs': [u1['ref'], u2['ref']],
        }
        windows.append(window)
    return windows


def parse_ref(ref):
    """Parse a single-line ref like 'luc. 1.5' → (book, line)."""
    nums = [int(x) for x in re.findall(r'\d+', ref)]
    if len(nums) >= 2:
        return nums[-2], nums[-1]
    return None, None


def parse_range_ref(ref):
    """Parse a ref that may be a range like 'luc. 1.1-luc. 1.2'.
    Returns (book, start_line, end_line)."""
    if '-' in ref:
        parts = ref.split('-', 1)
        nums_left = [int(x) for x in re.findall(r'\d+', parts[0])]
        nums_right = [int(x) for x in re.findall(r'\d+', parts[1])]
        if len(nums_left) >= 2 and len(nums_right) >= 2:
            book_start, line_start = nums_left[-2], nums_left[-1]
            book_end, line_end = nums_right[-2], nums_right[-1]
            if book_start == book_end:
                return book_start, line_start, line_end
            else:
                return book_start, line_start, line_start
    book, line = parse_ref(ref)
    if book is not None:
        return book, line, line
    return None, None, None


# ---------------------------------------------------------------------------
# Syntax channel: load pre-parsed data from syntax_latin.db
# ---------------------------------------------------------------------------

_SYNTAX_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "inverted_index", "syntax_latin.db",
)

_SYNTAX_PARSE_CACHE = {}


def _load_syntax_for_text(db_path, text_filename):
    """Load syntax parses from syntax_latin.db for a text.

    Results are cached at module level so repeated searches on the same
    text avoid re-reading the database.

    Returns dict: ref → {"lemmas": [...], "upos": [...], "heads": [...],
                          "deprels": [...], "feats": [...], "tokens": [...]}
    """
    if text_filename in _SYNTAX_PARSE_CACHE:
        return _SYNTAX_PARSE_CACHE[text_filename]

    if not os.path.exists(db_path):
        return {}

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT text_id FROM texts WHERE filename = ?", (text_filename,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {}

    text_id = row[0]
    cur.execute(
        "SELECT ref, tokens, lemmas, upos, heads, deprels, feats "
        "FROM syntax WHERE text_id = ?",
        (text_id,),
    )

    parses = {}
    for ref, tokens, lemmas, upos, heads, deprels, feats in cur.fetchall():
        parses[ref] = {
            "tokens": json.loads(tokens) if tokens else [],
            "lemmas": json.loads(lemmas) if lemmas else [],
            "upos": json.loads(upos) if upos else [],
            "heads": json.loads(heads) if heads else [],
            "deprels": json.loads(deprels) if deprels else [],
            "feats": json.loads(feats) if feats else [],
        }

    conn.close()
    _SYNTAX_PARSE_CACHE[text_filename] = parses
    return parses


def _compute_syntax_score(source_parse, target_parse):
    """Compute syntax similarity between two parsed lines.

    Mirrors compute_syntax_similarity() from syntax_parser.py but operates
    directly on the DB parse format (lists) without building SyntaxSentence
    objects, for efficiency in bulk comparison.

    Returns 0.0 if no shared lemmas; otherwise a score in [0, 1].
    """
    s_lemmas = source_parse["lemmas"]
    s_deprels = source_parse["deprels"]
    s_upos = source_parse["upos"]

    t_lemmas = target_parse["lemmas"]
    t_deprels = target_parse["deprels"]
    t_upos = target_parse["upos"]

    # Build lemma → (deprel, upos) maps, excluding punctuation
    s_roles = {}
    for i, lemma in enumerate(s_lemmas):
        if i < len(s_upos) and s_upos[i] not in ("PUNCT", "X") and lemma:
            s_roles[lemma.lower()] = (
                s_deprels[i] if i < len(s_deprels) else "",
                s_upos[i],
            )

    t_roles = {}
    for i, lemma in enumerate(t_lemmas):
        if i < len(t_upos) and t_upos[i] not in ("PUNCT", "X") and lemma:
            t_roles[lemma.lower()] = (
                t_deprels[i] if i < len(t_deprels) else "",
                t_upos[i],
            )

    shared = set(s_roles.keys()) & set(t_roles.keys())
    if not shared:
        return 0.0

    from backend.syntax_parser import get_deprel_category

    score = 0.0
    max_score = len(shared)

    for lemma in shared:
        s_deprel, s_pos = s_roles[lemma]
        t_deprel, t_pos = t_roles[lemma]

        if s_deprel == t_deprel:
            score += 1.0
        elif get_deprel_category(s_deprel) == get_deprel_category(t_deprel):
            score += 0.7
        elif s_pos == t_pos:
            score += 0.4

    # Structure signature bonus (core argument overlap)
    s_core = sorted(
        s_deprels[i]
        for i in range(len(s_deprels))
        if i < len(s_upos)
        and s_upos[i] not in ("PUNCT", "X")
        and get_deprel_category(s_deprels[i]) == "core"
    )
    t_core = sorted(
        t_deprels[i]
        for i in range(len(t_deprels))
        if i < len(t_upos)
        and t_upos[i] not in ("PUNCT", "X")
        and get_deprel_category(t_deprels[i]) == "core"
    )
    if s_core and t_core:
        overlap = len(set(s_core) & set(t_core))
        union = len(set(s_core) | set(t_core))
        if union > 0:
            score += (overlap / union) * 0.5
            max_score += 0.5

    return score / max_score if max_score > 0 else 0.0


# Pair-size gates removed: dictionary (inverted index), lemma_min1 (IDF
# pre-filter), and syntax (caching + multiprocessing) are now fast enough
# to run on any pair size.  All 9 channels always run.


def _score_syntax_chunk(args):
    """Worker function for parallel syntax scoring."""
    pairs, min_score = args
    hits = []
    for source_ref, source_parse, target_ref, target_parse in pairs:
        score = _compute_syntax_score(source_parse, target_parse)
        if score >= min_score:
            hits.append((source_ref, target_ref, score))
    return hits


def find_syntax_matches(source_units, target_units, source_id, target_id,
                        min_score=0.1, max_results=50000):
    """Find syntax matches between source and target using syntax_latin.db.

    Uses a lemma-inverted-index pruning strategy: only computes syntax
    similarity for pairs sharing at least one lemma, since pairs with
    no shared lemmas always score 0.0.

    Parallelized for large candidate sets using multiprocessing.

    Returns results in the same format as other channels.
    """
    source_parses = _load_syntax_for_text(_SYNTAX_DB_PATH, source_id)
    target_parses = _load_syntax_for_text(_SYNTAX_DB_PATH, target_id)

    if not source_parses or not target_parses:
        print(f"[SYNTAX] No syntax data for {source_id} or {target_id}")
        return []

    # Build ref → unit lookup for both texts
    source_by_ref = {u["ref"]: u for u in source_units}
    target_by_ref = {u["ref"]: u for u in target_units}

    # Build lemma → [target_ref] inverted index from parsed target data
    target_lemma_index = defaultdict(set)
    for ref, parse in target_parses.items():
        for i, lemma in enumerate(parse["lemmas"]):
            if (
                i < len(parse["upos"])
                and parse["upos"][i] not in ("PUNCT", "X")
                and lemma
            ):
                target_lemma_index[lemma.lower()].add(ref)

    # Collect all candidate pairs via shared lemmas
    candidate_pairs = []
    for source_ref, source_parse in source_parses.items():
        if source_ref not in source_by_ref:
            continue

        candidate_targets = set()
        for i, lemma in enumerate(source_parse["lemmas"]):
            if (
                i < len(source_parse["upos"])
                and source_parse["upos"][i] not in ("PUNCT", "X")
                and lemma
            ):
                candidate_targets |= target_lemma_index.get(lemma.lower(), set())

        for target_ref in candidate_targets:
            if target_ref not in target_by_ref:
                continue
            target_parse = target_parses.get(target_ref)
            if target_parse:
                candidate_pairs.append(
                    (source_ref, source_parse, target_ref, target_parse)
                )

    num_candidates = len(candidate_pairs)

    # Score candidates — use multiprocessing for large sets
    if num_candidates > 50000:
        import multiprocessing
        num_workers = min(multiprocessing.cpu_count(), 8)
        chunk_size = (num_candidates + num_workers - 1) // num_workers
        chunks = [
            candidate_pairs[i:i + chunk_size]
            for i in range(0, num_candidates, chunk_size)
        ]
        print(f"[SYNTAX] Parallel: {num_candidates:,} candidates, "
              f"{num_workers} workers, {chunk_size:,} per chunk")
        with multiprocessing.Pool(num_workers) as pool:
            chunk_results = pool.map(
                _score_syntax_chunk,
                [(chunk, min_score) for chunk in chunks],
            )
        scored_pairs = []
        for chunk_hits in chunk_results:
            scored_pairs.extend(chunk_hits)
    else:
        scored_pairs = []
        for source_ref, source_parse, target_ref, target_parse in candidate_pairs:
            score = _compute_syntax_score(source_parse, target_parse)
            if score >= min_score:
                scored_pairs.append((source_ref, target_ref, score))

    # Build result dicts
    results = []
    for source_ref, target_ref, score in scored_pairs:
        source_unit = source_by_ref[source_ref]
        target_unit = target_by_ref[target_ref]
        results.append({
            "source": {
                "ref": source_ref,
                "text": source_unit.get("text", ""),
                "tokens": source_unit.get("tokens", []),
                "lemmas": source_unit.get("lemmas", []),
                "highlight_indices": [],
            },
            "target": {
                "ref": target_ref,
                "text": target_unit.get("text", ""),
                "tokens": target_unit.get("tokens", []),
                "lemmas": target_unit.get("lemmas", []),
                "highlight_indices": [],
            },
            "score": score,
            "overall_score": score,
            "matched_words": [],
        })

    print(f"[SYNTAX] {len(source_parses)} source, {len(target_parses)} target parses; "
          f"{num_candidates:,} comparisons; {len(results)} matches (score >= {min_score})")

    # Keep top results by score
    if max_results > 0 and len(results) > max_results:
        results.sort(key=lambda r: r["overall_score"], reverse=True)
        results = results[:max_results]

    return results


def run_channel(channel_name, config, source_units, target_units,
                matcher, scorer, source_id, target_id,
                source_path=None, target_path=None):
    """Run a single search channel and return scored results."""
    match_type = config.get("match_type", "lemma")
    settings = dict(config)

    if match_type == "syntax":
        # Syntax channel uses its own scoring from syntax_latin.db
        max_results = config.get("max_results", 50000)
        min_score = settings.get("min_score", 0.1)
        results = find_syntax_matches(
            source_units, target_units,
            source_id, target_id,
            min_score=min_score,
            max_results=max_results,
        )
        return results

    if match_type == "semantic":
        from backend.semantic_similarity import find_semantic_matches
        if source_path:
            settings["source_text_path"] = source_path
        if target_path:
            settings["target_text_path"] = target_path
        matches, _ = find_semantic_matches(source_units, target_units, settings)
    elif match_type == "dictionary":
        from backend.semantic_similarity import find_dictionary_matches
        matches, _ = find_dictionary_matches(source_units, target_units, settings)
    elif match_type == "sound":
        matches, _ = matcher.find_sound_matches(source_units, target_units, settings)
    elif match_type == "edit_distance":
        matches, _ = matcher.find_edit_distance_matches(
            source_units, target_units, settings
        )
    elif match_type == "rare_word":
        try:
            from backend.blueprints.hapax import find_rare_word_matches_direct
            max_occ = settings.get("rare_word_max_occurrences", 50)
            matches = find_rare_word_matches_direct(
                source_units, target_units,
                language=settings.get("language", "la"),
                max_occurrences=max_occ,
            )
        except (ImportError, AttributeError):
            matches = []
    else:
        # lemma or exact
        matches, _ = matcher.find_matches(source_units, target_units, settings, None)

    if not matches:
        return []

    # IDF pre-filter: when a per-channel cap is set and the raw match count
    # far exceeds it, estimate each match's score by summing IDF of matched
    # lemmas and keep only the top candidates.  This avoids scoring hundreds
    # of thousands of low-value matches (the main bottleneck for lemma_min1).
    max_results = config.get("max_results", 0)
    if max_results > 0 and len(matches) > max_results * 2:
        from collections import Counter
        lemma_freq = Counter()
        for u in source_units:
            for lem in set(u.get('lemmas', [])):
                lemma_freq[lem] += 1
        for u in target_units:
            for lem in set(u.get('lemmas', [])):
                lemma_freq[lem] += 1
        total_docs = len(source_units) + len(target_units)

        def _quick_idf(match):
            return sum(
                math.log((total_docs + 1) / (lemma_freq.get(l, 1) + 1)) + 1
                for l in match.get('matched_lemmas', [])
            )

        for m in matches:
            m['_quick_score'] = _quick_idf(m)
        matches.sort(key=lambda m: m['_quick_score'], reverse=True)
        kept = max_results * 4  # 4x buffer for distance-factor reranking
        print(f"[{channel_name.upper()}] IDF pre-filter: {len(matches):,} → {kept:,} matches")
        matches = matches[:kept]

    scored = scorer.score_matches(
        matches, source_units, target_units, settings, source_id, target_id
    )

    # Per-channel result cap: retain only the top-scoring results from each
    # channel before fusion.
    if max_results > 0 and len(scored) > max_results:
        scored.sort(
            key=lambda r: r.get("overall_score") or r.get("score") or 0,
            reverse=True,
        )
        scored = scored[:max_results]

    return scored


def fuse_results(channel_results):
    """Combine results from multiple channels using weighted score fusion.

    For each (source_ref, target_ref) pair:
      fused_score = sum(channel_score * channel_weight) + convergence_bonus * (N-1)
    where N = number of channels that found the pair.
    """
    pair_scores = defaultdict(lambda: {
        "score": 0.0,
        "channels": [],
        "best_result": None,
        "best_score": 0.0,
        "all_source_highlights": set(),
        "all_target_highlights": set(),
        "all_matched_words": {},
    })

    for ch_name, results in channel_results.items():
        weight = CHANNEL_WEIGHTS.get(ch_name, 1.0)
        for r in results:
            rs = r.get("source", {}).get("ref", "")
            rt = r.get("target", {}).get("ref", "")
            key = (rs, rt)
            raw_score = r.get("overall_score") or r.get("score") or 0
            pair_scores[key]["score"] += raw_score * weight
            pair_scores[key]["channels"].append(ch_name)

            # Accumulate highlight indices from all channels
            src = r.get("source", {})
            tgt = r.get("target", {})
            for idx in src.get("highlight_indices", []):
                pair_scores[key]["all_source_highlights"].add(idx)
            for idx in tgt.get("highlight_indices", []):
                pair_scores[key]["all_target_highlights"].add(idx)

            # Accumulate matched words (dedup by lemma, prefer entries with source_word)
            for mw in r.get("matched_words", []):
                lemma = mw.get("lemma", "")
                if not lemma:
                    continue
                existing = pair_scores[key]["all_matched_words"].get(lemma)
                if existing is None or (not existing.get("source_word") and mw.get("source_word")):
                    pair_scores[key]["all_matched_words"][lemma] = mw

            # Keep the result with the highest individual score for display
            if raw_score > pair_scores[key]["best_score"]:
                pair_scores[key]["best_result"] = r
                pair_scores[key]["best_score"] = raw_score

    # Apply convergence bonus
    for key, info in pair_scores.items():
        n = len(info["channels"])
        if n > 1:
            info["score"] += CONVERGENCE_BONUS * (n - 1)

    # Sort by fused score and build output
    sorted_pairs = sorted(pair_scores.items(), key=lambda x: x[1]["score"], reverse=True)
    merged = []
    for (rs, rt), info in sorted_pairs:
        result = dict(info["best_result"]) if info["best_result"] else {}
        # Merge highlights from all channels into the result
        if "source" in result:
            result["source"] = dict(result["source"])
            result["source"]["highlight_indices"] = sorted(
                info["all_source_highlights"]
            )
        if "target" in result:
            result["target"] = dict(result["target"])
            result["target"]["highlight_indices"] = sorted(
                info["all_target_highlights"]
            )
        result["matched_words"] = list(info["all_matched_words"].values())
        result["fused_score"] = round(info["score"], 4)
        result["channels"] = info["channels"]
        result["channel_count"] = len(info["channels"])
        merged.append(result)

    return merged


def merge_line_and_window(line_results, window_results):
    """Merge line and window results with smart dedup.

    Line results come first (preserving precision). Window results are
    appended only if they contain at least one source×target line pair
    not already found in line results (i.e., not fully subsumed).
    """
    # Build set of (book, line, book, line) tuples from line results
    line_ref_tuples = set()
    for r in line_results:
        rs = r.get("source", {}).get("ref", "")
        rt = r.get("target", {}).get("ref", "")
        sb, sl = parse_ref(rs)
        tb, tl = parse_ref(rt)
        if sb is not None and tb is not None:
            line_ref_tuples.add((sb, sl, tb, tl))

    # Only keep window results that have novel line-pair coverage
    merged = list(line_results)
    for r in window_results:
        rs = r.get("source", {}).get("ref", "")
        rt = r.get("target", {}).get("ref", "")
        rs_b, rs_start, rs_end = parse_range_ref(rs)
        rt_b, rt_start, rt_end = parse_range_ref(rt)

        fully_subsumed = True
        if rs_b is not None and rt_b is not None:
            for sl in range(rs_start, rs_end + 1):
                for tl in range(rt_start, rt_end + 1):
                    if (rs_b, sl, rt_b, tl) not in line_ref_tuples:
                        fully_subsumed = False
                        break
                if not fully_subsumed:
                    break
        else:
            fully_subsumed = False

        if not fully_subsumed:
            merged.append(r)

    return merged


def _run_channels_sequential(channels, configs, source_units, target_units,
                             matcher, scorer, source_id, target_id,
                             source_path, target_path, phase_label,
                             progress_callback):
    """Run channels sequentially in the main process.

    The heavy channels (edit_distance, sound) use internal multiprocessing
    to parallelize their own work across cores, so running channels
    sequentially here avoids nested parallelism overhead.
    """
    channel_results = {}
    total = len(channels)

    for i, ch_name in enumerate(channels):
        if progress_callback:
            progress_callback(i + 1, total, ch_name, phase_label)

        config = configs[ch_name]
        results = run_channel(
            ch_name, config, source_units, target_units,
            matcher, scorer, source_id, target_id,
            source_path=source_path, target_path=target_path,
        )
        if results:
            channel_results[ch_name] = results

    return channel_results


def iter_fusion_search(source_units, target_units, matcher, scorer,
                       source_id, target_id, language='la',
                       mode='merged', max_results=5000,
                       source_path=None, target_path=None,
                       user_settings=None):
    """Generator version of run_fusion_search for progressive SSE streaming.

    Yields (event_type, data) tuples as the search progresses:
        ("channel_start", {channel, step, total, phase})
        ("channel_done",  {channel, count, step, total, phase})
        ("intermediate",  {results, total_results, channels_done, phase})
        ("complete",      {results, total_results})

    Uses CHANNEL_ORDER (fast channels first) so intermediate results
    appear within seconds of starting the search.
    """
    user_settings = user_settings or {}

    # Build per-channel configs with language override and user settings
    configs = {}
    for name, cfg in CHANNEL_CONFIGS.items():
        c = dict(cfg)
        if "language" in c:
            c["language"] = language
        # Merge user settings (e.g., use_meter) into each channel config
        for k in ('use_meter',):
            if user_settings.get(k):
                c[k] = user_settings[k]
        configs[name] = c

    # --- Pass 1: Line-level (all channels, fast-first order) ---
    line_channel_results = {}
    line_channels = [ch for ch in CHANNEL_ORDER if ch in configs]
    total_line = len(line_channels)

    for i, ch_name in enumerate(line_channels):
        yield ("channel_start", {
            "channel": ch_name,
            "step": i + 1,
            "total": total_line,
            "phase": "line",
        })

        results = run_channel(
            ch_name, configs[ch_name], source_units, target_units,
            matcher, scorer, source_id, target_id,
            source_path=source_path, target_path=target_path,
        )
        count = len(results) if results else 0
        if results:
            line_channel_results[ch_name] = results

        yield ("channel_done", {
            "channel": ch_name,
            "count": count,
            "step": i + 1,
            "total": total_line,
            "phase": "line",
            "skipped": False,
        })

        # Send intermediate fused results after each channel that found matches.
        # Skip when count==0 (no new data to fuse, saves bandwidth).
        # Cap intermediates at 500 (preview only) to avoid huge JSON payloads;
        # the full max_results set is sent in the final "complete" event.
        if count > 0 and line_channel_results:
            fused = fuse_results(line_channel_results)
            preview_cap = min(max_results, 500) if max_results > 0 else 500
            top = fused[:preview_cap]
            yield ("intermediate", {
                "results": top,
                "total_results": len(fused),
                "channels_done": list(line_channel_results.keys()),
                "phase": "line",
            })

    line_fused = fuse_results(line_channel_results)

    if mode == 'line':
        final = line_fused[:max_results] if max_results > 0 else line_fused
        yield ("complete", {"results": final, "total_results": len(line_fused)})
        return

    # --- Pass 2: Window-level (co-occurrence channels only) ---
    source_windows = make_window_units(source_units)
    target_windows = make_window_units(target_units)
    window_channel_results = {}
    window_channels = [ch for ch in WINDOW_CHANNELS if ch in configs]
    total_window = len(window_channels)

    for i, ch_name in enumerate(window_channels):
        yield ("channel_start", {
            "channel": ch_name,
            "step": i + 1,
            "total": total_window,
            "phase": "window",
        })

        results = run_channel(
            ch_name, configs[ch_name], source_windows, target_windows,
            matcher, scorer, source_id, target_id,
            source_path=source_path, target_path=target_path,
        )
        count = len(results) if results else 0
        if results:
            window_channel_results[ch_name] = results

        yield ("channel_done", {
            "channel": ch_name,
            "count": count,
            "step": i + 1,
            "total": total_window,
            "phase": "window",
        })

    window_fused = fuse_results(window_channel_results)

    if mode == 'window':
        final = window_fused[:max_results] if max_results > 0 else window_fused
        yield ("complete", {"results": final, "total_results": len(window_fused)})
        return

    # --- Merge: line results first, then novel window results ---
    merged = merge_line_and_window(line_fused, window_fused)
    final = merged[:max_results] if max_results > 0 else merged
    yield ("complete", {"results": final, "total_results": len(merged)})


def run_fusion_search(source_units, target_units, matcher, scorer,
                      source_id, target_id, language='la',
                      mode='merged', max_results=500,
                      source_path=None, target_path=None,
                      progress_callback=None):
    """Run two-pass weighted fusion search.

    Pass 1 (line-level): All 9 channels run on individual verse lines.
    Pass 2 (window-level): Lexical channels only run on 2-line sliding
        windows, capturing enjambed allusions. Sub-lexical and
        distributional channels are omitted because their pairwise
        token comparisons are already exhaustive at the line level.

    Args:
        source_units: Processed line units for source text
        target_units: Processed line units for target text
        matcher: Matcher instance
        scorer: Scorer instance
        source_id: Source text filename
        target_id: Target text filename
        language: Language code ('la', 'grc', 'en')
        mode: 'line' (lines only), 'window' (windows only), 'merged' (both)
        max_results: Maximum results to return (0 = unlimited)
        source_path: Full path to source .tess file (for semantic)
        target_path: Full path to target .tess file (for semantic)
        progress_callback: Optional fn(step, total, channel_name, phase) for SSE

    Returns:
        List of result dicts sorted by fused_score descending.
    """
    # Update language in all configs
    configs = {}
    for name, cfg in CHANNEL_CONFIGS.items():
        c = dict(cfg)
        if "language" in c:
            c["language"] = language
        configs[name] = c

    # --- Pass 1: Line-level (all channels) ---
    line_channels = [ch for ch in ALL_CHANNELS if ch in configs]

    line_channel_results = _run_channels_sequential(
        line_channels, configs, source_units, target_units,
        matcher, scorer, source_id, target_id,
        source_path, target_path, "line",
        progress_callback,
    )
    line_fused = fuse_results(line_channel_results)

    if mode == 'line':
        return line_fused[:max_results] if max_results > 0 else line_fused

    # --- Pass 2: Window-level (lexical channels only) ---
    # Only lexical channels benefit from windowing — see module docstring
    # for the channel-appropriate granularity rationale.
    window_channels = [ch for ch in WINDOW_CHANNELS if ch in configs]

    source_windows = make_window_units(source_units)
    target_windows = make_window_units(target_units)

    window_channel_results = _run_channels_sequential(
        window_channels, configs, source_windows, target_windows,
        matcher, scorer, source_id, target_id,
        source_path, target_path, "window",
        progress_callback,
    )
    window_fused = fuse_results(window_channel_results)

    if mode == 'window':
        return window_fused[:max_results] if max_results > 0 else window_fused

    # --- Merge: line results first, then novel window results ---
    merged = merge_line_and_window(line_fused, window_fused)

    return merged[:max_results] if max_results > 0 else merged
