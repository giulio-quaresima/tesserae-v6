"""
Tesserae V6 — Fusion Search Engine (Config K, Feb 28 2026)

Implements multi-channel weighted score fusion with a two-pass
line/window architecture for intertext detection.

Architecture
------------
The search operates in two passes over each text pair:

  Pass 1 — Line-level: All 9 channels run on individual verse lines.
      This is the primary search, providing full 9-channel coverage.

  Pass 2 — Window-level: A subset of channels (lemma, lemma_min1,
      rare_word, dictionary) run on sliding windows of 2 consecutive
      lines, capturing enjambed allusions split across line breaks.

Channel taxonomy
----------------
Channels are classified by the *level of linguistic representation*
at which they operate, which determines their behavior under windowing:

  LEXICAL channels (lemma, exact, rare_word, lemma_min1) match on the
  identity of word forms or lemmata.

  SUB-LEXICAL channels (edit_distance, sound) match on character-level
  similarity (Levenshtein distance, trigram overlap).

  DISTRIBUTIONAL channels (semantic, dictionary) match on vector
  similarity or curated synonym pairs.

  STRUCTURAL channels (syntax) match on dependency-tree patterns.

Scoring — Three-layer rarity system
------------------------------------
  base = sum(channel_score_i * weight_i)
  fused = base * mult^2 + conv * mult^conv_power

Layer 1 — Base score penalty (mult^2):
  mult = piecewise_linear(geom_mean_idf, idf_floor, idf_threshold)
  Applied as mult^2 to the base score. Common-word pairs get heavily
  penalized (e.g., geom_idf=0.36 → mult=0.33 → mult^2=0.11).

Layer 2 — IDF-weighted convergence:
  Each channel's convergence contribution is weighted by
  min(1.0, geom_mean_idf)^2, preventing common-word pairs from
  accumulating large bonuses despite matching on many channels.

Layer 3 — Rarity boost for rare multi-channel matches:
  When geom_idf exceeds the threshold, mult rises above 1.0 via a
  log curve, scaled by min(channel_factor, word_factor). Requires
  both multiple channels AND multiple distinct words for a boost.

The geometric mean IDF is computed from corpus-wide document frequencies
(1,429 Latin texts), with surface-form deduplication by (source_word,
target_word) to prevent inflected forms from inflating the mean.

Channel weights are from Config K (grid-search optimized, Feb 28 2026).
"""

import json
import math
import os
import re
import sqlite3
from collections import defaultdict


# ---------------------------------------------------------------------------
# Config K channel weights (Feb 28 2026)
#
# These weights were determined by grid-search optimization across Configs
# A through K, evaluated on 5 Latin benchmarks (862 gold-standard parallels).
# The optimizer (evaluation/scripts/run_weight_optimization.py v8) swept
# 34,992 weight combinations and 180 IDF curve parameter sets at each stage.
#
# Three-layer rarity scoring system
# ----------------------------------
# The scoring formula applies three independent mechanisms to suppress
# common-word noise while preserving (and boosting) rare-word matches.
# All three layers use the same geometric mean corpus-IDF as input.
#
# Layer 1 — Base score penalty (mult^2):
#   The raw weighted sum is multiplied by mult^2, where mult is a piecewise
#   linear function from idf_floor (0.2) at geom_idf < 0.1 to 1.0 at the
#   threshold (1.5). Common-word pairs are heavily penalized: a pair with
#   geom_idf=0.36 (e.g. "tum vero") gets mult=0.33, so mult^2=0.11 — an
#   89% reduction. Pairs with geom_idf >= threshold are unpenalized (1.0).
#
# Layer 2 — IDF-weighted convergence:
#   Each channel's contribution to the convergence bonus is scaled by
#   min(1.0, geom_mean_idf)^2 instead of counting as a flat 1.0. This
#   prevents common-word pairs that happen to match on many channels from
#   accumulating large bonuses: "tum vero" matching on 6 channels gets
#   weighted_n = 6 * 0.13 = 0.78, yielding zero convergence bonus (needs
#   weighted_n > 1.0). Distinctive pairs like "centum angues" with
#   geom_idf > 1.0 are unaffected (capped at 1.0 per channel).
#
# Layer 3 — Rarity boost for multi-channel rare matches:
#   When geom_idf exceeds the threshold, the multiplier rises above 1.0
#   via a log curve: 1.0 + boost_weight * channel_factor * log(geom_idf /
#   threshold), capped at boost_cap (2.0). The channel_factor is
#   (n_scoring_channels - 1) / 5, so single-channel noise (n=1, factor=0)
#   gets no boost — only multi-channel convergence on rare vocabulary is
#   promoted. This rewards the most distinctive, well-attested allusions.
#
# Combined effect on key test cases (from optimizer evaluation):
#   "tum vero"       (common): geom_idf=0.36, rank went from #37 to #903
#   "centum angues"  (rare):   geom_idf>3.0,  stable at #4
#   "Acheronta movebo" (rare): stable at #10
#   Top 100: 0% common-word matches; function-word noise eliminated.
#   Total recall: 784/862 (91.0%, unchanged by rarity scoring).
# ---------------------------------------------------------------------------
CHANNEL_WEIGHTS = {
    "edit_distance": 2.0,   # sub-lexical: Levenshtein fuzzy match (highest for phonetic echoes)
    "sound": 4.0,           # sub-lexical: character trigram overlap (most heavily weighted —
                            #   sound echoes are strong evidence of intentional allusion)
    "exact": 1.0,           # lexical: identical surface forms (low — subsumed by lemma)
    "lemma": 2.0,           # lexical: shared dictionary headwords (core V3-style matching)
    "dictionary": 0.5,      # distributional: curated V3 synonym pairs (low — broad recall,
                            #   many false positives without co-occurrence)
    "semantic": 1.2,        # distributional: SPhilBERTa cosine similarity (moderate —
                            #   good at catching paraphrase but noisy at low thresholds)
    "rare_word": 2.0,       # lexical: shared low-frequency lemmata (high — rare word sharing
                            #   is strong allusion evidence; min_matches=1 is sufficient)
    "syntax": 0.3,          # structural: dependency pattern match (low — supplements other
                            #   channels but unreliable as primary signal)
    "lemma_min1": 0.3,      # lexical: single shared lemma (low — very high recall, very
                            #   noisy; serves as a catch-all for otherwise missed pairs)
}

# Bonus added for each additional channel beyond the first that confirms
# a pair, rewarding cross-channel convergence as evidence of a true allusion.
# The raw bonus per extra channel is 0.75 * idf_weight, where idf_weight
# is min(1.0, geom_mean_idf)^2 (Layer 2). With squared IDF weighting,
# 0.75 is safe: even 8 extra channels on a common-word pair contribute
# little (0.75 * 8 * 0.13 = 0.78), while 4 extra channels on a distinctive
# pair contribute 0.75 * 4 * 1.0 = 3.0 — a meaningful boost.
CONVERGENCE_BONUS = 0.75

# ---------------------------------------------------------------------------
# Rarity scoring parameters: graduated corpus-IDF multiplier
# ---------------------------------------------------------------------------
# The rarity multiplier uses the GEOMETRIC mean of corpus-wide IDF values
# for matched lemmas. Geometric mean penalizes pairs where even ONE word
# is ultra-common: "sum" (idf=0.007) + "locus" (idf=3.0) → geom=0.15
# (penalized) vs arithmetic mean=1.50 (not penalized). This is critical
# because function words like "est", "et", "in" appear in >95% of the
# 1429 Latin texts, making any pair containing them almost certainly noise.
#
# Entries with df=0 (surface forms not in the inverted index, e.g. "auras"
# instead of canonical "aura") are SKIPPED — treating them as ultra-rare
# would inflate the geometric mean and mask penalties for their common
# companions.
#
# Piecewise linear curve mapping geom_mean_idf → multiplier:
#   geom_idf < 0.1           → idf_floor (harshest penalty, near-stopwords)
#   0.1 ≤ geom_idf < thresh  → linear ramp from (idf_floor + 0.1) to 1.0
#   geom_idf ≥ thresh        → ≥ 1.0 (no penalty; rarity boost for Layer 3)
# ---------------------------------------------------------------------------

# Multiplier floor: the minimum rarity multiplier applied to pairs whose
# geometric mean IDF is below 0.1 (i.e., all matched lemmata are extremely
# common — words appearing in >90% of texts). Since mult is squared (Layer 1),
# the effective floor is 0.2^2 = 0.04 (96% score reduction).
RARITY_IDF_FLOOR = 0.2

# IDF threshold: the geometric mean IDF at which the multiplier reaches 1.0
# (no penalty). With 1429 Latin texts, IDF = log(1429/df):
#   df=954 (67% of texts) → idf=0.40 (penalized)
#   df=314 (22% of texts) → idf=1.51 (at threshold, no penalty)
#   df=50  (3.5% of texts) → idf=3.35 (boosted if multi-channel)
# Value of 1.5 means words appearing in more than ~22% of texts get penalized.
RARITY_IDF_THRESHOLD = 1.5

# Exponent for the base score penalty: base_score * multiplier^power.
# Higher values make the penalty steeper for common words without affecting
# rare words (mult=1.0 → 1.0^anything = 1.0). The squaring in Layer 2
# (IDF-weighted convergence) uses a fixed exponent of 2.
RARITY_PENALTY_POWER = 2.0

# Exponent applied to the rarity multiplier when scaling the convergence
# bonus: conv_mult = multiplier^power. With power=1.0, the convergence bonus
# gets the same rarity scaling as the base score (before squaring). Higher
# powers would penalize convergence more aggressively. Optimizer found 1.0
# optimal — further convergence penalty on top of squared IDF weighting
# (Layer 2) provides no benefit.
CONVERGENCE_IDF_POWER = 1.0

# Min-IDF gate: an additional penalty if ANY single matched lemma has corpus
# IDF below the threshold. This would catch pairs where the geometric mean
# is pulled up by moderate-frequency companions but one word is truly
# ubiquitous (e.g., "per" in all 1429 texts). DISABLED (threshold=0.0):
# the optimizer grid search found no recall/ranking benefit — the geometric
# mean already handles this case via its sensitivity to individual outliers.
RARITY_MIN_IDF_THRESHOLD = 0.0
RARITY_MIN_IDF_PENALTY = 1.0       # 1.0 = no effect (gate is disabled)

# Rarity boost (Layer 3): for pairs with geom_idf above the threshold,
# the multiplier exceeds 1.0 to actively promote rare multi-channel matches.
# Formula: 1.0 + boost_weight * channel_factor * log(geom_idf / threshold)
# where channel_factor = min(1.0, (n_scoring_channels - 1) / 5).
# The log curve provides diminishing returns for extremely rare words,
# preventing runaway scores. The channel_factor ensures single-channel
# matches (n=1, factor=0) get zero boost — only multi-channel convergence
# on rare vocabulary is promoted. The cap prevents any multiplier from
# exceeding 2.0 regardless of how rare the vocabulary is.
# Rarity multiplier ramp start offset: the multiplier at the bottom of the
# linear ramp (geom_idf == RARITY_NEAR_STOPWORD_CUTOFF) is idf_floor + this
# value, avoiding a discontinuity at the floor/ramp boundary.
RARITY_RAMP_OFFSET = 0.1

# Geometric mean IDF below this value is treated as near-stopword territory
# (flat at idf_floor). Between this value and idf_threshold, the multiplier
# ramps linearly from (idf_floor + RARITY_RAMP_OFFSET) to 1.0.
RARITY_NEAR_STOPWORD_CUTOFF = 0.1

RARITY_BOOST_WEIGHT = 0.5          # scaling factor on the log-curve boost
RARITY_BOOST_CAP = 2.0             # hard ceiling on multiplier (prevents runaway)

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
        "min_matches": 1,
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


# ---------------------------------------------------------------------------
# Corpus-IDF utilities for graduated rarity multiplier
# ---------------------------------------------------------------------------

_corpus_doc_freq_cache = {}
_total_texts_cache = {}


def _get_corpus_doc_freqs(lemmas, language='la'):
    """Batch-fetch corpus-wide document frequencies, with caching.

    Reuses get_document_frequencies_batch() from hapax.py which queries the
    inverted index (la_index.db / grc_index.db). The hapax function handles
    u/v expansion internally for Latin.

    IMPORTANT: For Latin, deduplicates u/v variants before batch querying
    to avoid a collision bug in get_document_frequencies_batch where the
    expanded_map overwrites entries when two input lemmas are u/v variants
    of each other (e.g., querying {'uero', 'vero'} causes 'uero' → df=0).

    Returns dict: lemma → document count (0 if not found).
    """
    uncached = [l for l in lemmas if l not in _corpus_doc_freq_cache]
    if uncached:
        from backend.blueprints.hapax import get_document_frequencies_batch

        if language == 'la':
            # Deduplicate u/v variants: keep only one canonical form per
            # variant group. Map all variants back to the same DF result.
            canonical = {}  # u-normalized form → first lemma seen
            query_set = set()
            for l in uncached:
                norm = l.replace('v', 'u').replace('j', 'i')
                if norm not in canonical:
                    canonical[norm] = l
                    query_set.add(l)
                # else: l is a u/v variant of an already-queued lemma

            batch_result = get_document_frequencies_batch(query_set, language)

            # Populate cache for all uncached lemmas, including variants
            for l in uncached:
                norm = l.replace('v', 'u').replace('j', 'i')
                canon_lemma = canonical[norm]
                _corpus_doc_freq_cache[l] = batch_result.get(canon_lemma, 0)
        else:
            batch_result = get_document_frequencies_batch(set(uncached), language)
            for l in uncached:
                _corpus_doc_freq_cache[l] = batch_result.get(l, 0)

    return {l: _corpus_doc_freq_cache.get(l, 0) for l in lemmas}


def _get_total_texts(language='la'):
    """Get total text count from inverted index (cached)."""
    if language not in _total_texts_cache:
        try:
            from backend.inverted_index import get_connection
            conn = get_connection(language)
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM texts')
                _total_texts_cache[language] = cursor.fetchone()[0]
            else:
                # Fallback: known corpus sizes
                _total_texts_cache[language] = {'la': 1429, 'grc': 691}.get(
                    language, 1000)
        except Exception:
            _total_texts_cache[language] = {'la': 1429, 'grc': 691}.get(
                language, 1000)
    return _total_texts_cache[language]


def fuse_results(channel_results, weights=None, convergence_bonus=None,
                  idf_floor=None, idf_threshold=None,
                  convergence_idf_power=None, min_idf_threshold=None,
                  min_idf_penalty=None, language='la'):
    """Combine results from multiple channels using weighted score fusion.

    Three-layer rarity scoring for each (source_ref, target_ref) pair:

      base = sum(channel_score * channel_weight)
      mult = piecewise_linear(geom_mean_idf, idf_floor, threshold)
      idf_weight = min(1.0, geom_mean_idf)^2                   [Layer 2]
      weighted_n = n_scoring_channels * idf_weight              [Layer 2]
      conv = convergence_bonus * max(0, weighted_n - 1)         [Layer 2]
      fused = base * mult^penalty_power + conv * mult^conv_power

    Layer 3 boost: when geom_idf >= threshold, mult rises above 1.0 via
    log curve scaled by min(channel_factor, word_factor), requiring both
    multiple channels and multiple distinct words.

    Optional overrides allow testing different parameter configurations
    without modifying module globals (used by weight optimization).
    """
    _weights = weights if weights is not None else CHANNEL_WEIGHTS
    _convergence_bonus = convergence_bonus if convergence_bonus is not None else CONVERGENCE_BONUS
    _idf_floor = idf_floor if idf_floor is not None else RARITY_IDF_FLOOR
    _idf_threshold = idf_threshold if idf_threshold is not None else RARITY_IDF_THRESHOLD
    _conv_idf_power = convergence_idf_power if convergence_idf_power is not None else CONVERGENCE_IDF_POWER
    _min_idf_threshold = min_idf_threshold if min_idf_threshold is not None else RARITY_MIN_IDF_THRESHOLD
    _min_idf_penalty = min_idf_penalty if min_idf_penalty is not None else RARITY_MIN_IDF_PENALTY
    _rarity_boost_weight = RARITY_BOOST_WEIGHT
    _rarity_boost_cap = RARITY_BOOST_CAP
    _penalty_power = RARITY_PENALTY_POWER

    pair_scores = defaultdict(lambda: {
        "score": 0.0,
        "channels": [],
        "n_scoring_channels": 0,  # channels with raw_score > 0
        "best_result": None,
        "best_score": 0.0,
        "all_source_highlights": set(),
        "all_target_highlights": set(),
        "all_matched_words": {},
    })

    for ch_name, results in channel_results.items():
        weight = _weights.get(ch_name, 1.0)
        for r in results:
            rs = r.get("source", {}).get("ref", "")
            rt = r.get("target", {}).get("ref", "")
            key = (rs, rt)
            raw_score = r.get("overall_score") or r.get("score") or 0
            pair_scores[key]["score"] += raw_score * weight
            pair_scores[key]["channels"].append(ch_name)
            if raw_score > 0:
                pair_scores[key]["n_scoring_channels"] += 1

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

    # ===================================================================
    # RARITY SCORING: Three-layer system applied to every fused pair
    # ===================================================================
    #
    # This section implements all three layers of rarity scoring in a
    # single pass over all pairs, optimized to avoid per-pair function
    # call overhead (~100K pairs typical; inlining reduced runtime from
    # ~400s to ~58s for Aeneid x Met).
    #
    # Final formula for each pair:
    #   fused_score = base_score * mult^2 + conv_score * mult^power
    # where:
    #   base_score  = sum of (channel_score * channel_weight) across channels
    #   mult        = rarity multiplier from Layer 1 (piecewise linear on geom_idf)
    #                 OR rarity boost from Layer 3 (log curve, for rare words)
    #   conv_score  = convergence_bonus * (weighted_n - 1.0)   [Layer 2]
    #   weighted_n  = n_scoring_channels * min(1.0, geom_idf)^2  [Layer 2]
    #   power       = CONVERGENCE_IDF_POWER (currently 1.0)
    #
    # ===================================================================

    # --- Pre-fetch corpus document frequencies in one batch ---
    # Collect every unique lemma across all pairs (excluding sub-lexical
    # fragments like [que], [nti] from sound/edit_distance channels),
    # then query the inverted index once. This avoids per-pair DB queries
    # (which would mean ~100K separate queries for large text pairs).
    # NOTE: We include entries with idf=0 (from rare_word, semantic, etc.)
    # because they still have valid lemmas whose corpus df is needed for
    # rarity scoring. Only sub-lexical fragments (keys starting with '[')
    # are excluded.
    all_lexical_lemmas = set()
    for key, info in pair_scores.items():
        for lemma, mw in info["all_matched_words"].items():
            if lemma and not lemma.startswith('['):
                all_lexical_lemmas.add(lemma)
    total_texts = _get_total_texts(language) if all_lexical_lemmas else 1429
    doc_freq_map = _get_corpus_doc_freqs(list(all_lexical_lemmas), language) if all_lexical_lemmas else {}

    # Pre-compute constants used in the inner loop to avoid repeated
    # arithmetic on every iteration.
    _log_total = math.log(total_texts)        # log(N) for IDF = log(N) - log(df)
    _cutoff = RARITY_NEAR_STOPWORD_CUTOFF     # geom_idf below this → flat at floor
    _ramp_offset = RARITY_RAMP_OFFSET         # offset above floor at ramp start
    _ramp_start = _idf_floor + _ramp_offset   # multiplier at geom_idf = cutoff
    _ramp_range = 1.0 - _ramp_start           # span of the linear ramp
    _thresh_range = _idf_threshold - _cutoff   # IDF span of the linear ramp

    for key, info in pair_scores.items():
        # ---------------------------------------------------------------
        # LAYER 1: Compute geometric mean IDF and piecewise multiplier
        # ---------------------------------------------------------------
        # For each matched lemma with nonzero IDF, compute corpus IDF =
        # log(N/df), then take the geometric mean. Map to a multiplier
        # via the same piecewise linear curve defined in the constants.
        mw_dict = info["all_matched_words"]
        # Collect corpus IDFs for all lexical entries (not sub-lexical
        # fragments). Deduplicate by (source_word, target_word) to avoid
        # counting both inflected surface forms (e.g., "pugnas" df=1) and
        # canonical lemmas (e.g., "pugna" df=596) for the same word —
        # keep the canonical form (highest df) for accurate rarity scoring.
        word_pair_best = {}  # (src_word, tgt_word) -> (corpus_idf, df)
        for lemma, mw in mw_dict.items():
            if lemma.startswith('['):
                continue  # sub-lexical fragment
            df = doc_freq_map.get(lemma, 0)
            if df <= 0:
                continue  # not in inverted index
            cidf = _log_total - math.log(df)
            sw = mw.get('source_word', '')
            tw = mw.get('target_word', '')
            word_key = (sw, tw) if (sw or tw) else (lemma,)
            existing = word_pair_best.get(word_key)
            if existing is None or df > existing[1]:
                word_pair_best[word_key] = (cidf, df)
        corpus_idfs = [cidf for cidf, _ in word_pair_best.values()]
        n_unique_words = len(corpus_idfs)  # distinct lexical words matched

        if corpus_idfs:
            # Geometric mean via exp(mean(log(x))), with floor of 0.001
            # to avoid log(0) for words with corpus IDF very near zero
            log_sum = 0.0
            for cidf in corpus_idfs:
                log_sum += math.log(cidf) if cidf > 0.001 else math.log(0.001)
            geom_mean_idf = math.exp(log_sum / len(corpus_idfs))

            # Piecewise multiplier: maps geom_mean_idf to [idf_floor, 1.0]
            # for common words, or > 1.0 for rare multi-channel matches
            if geom_mean_idf < _cutoff:
                # Zone 1: Near-stopwords. Flat at idf_floor (0.2).
                # Examples: "est" (idf≈0.01), "et" (idf≈0.03)
                multiplier = _idf_floor
            elif geom_mean_idf < _idf_threshold:
                # Zone 2: Graduated penalty. Linear ramp from 0.3 to 1.0.
                # Example: "tum vero" with geom_idf=0.36 → t=0.19 → mult=0.33
                t = (geom_mean_idf - _cutoff) / _thresh_range
                multiplier = _ramp_start + t * _ramp_range
            else:
                # -------------------------------------------------------
                # LAYER 3: Rarity BOOST for rare multi-channel matches
                # -------------------------------------------------------
                # When geom_idf exceeds the threshold, the vocabulary is
                # rare enough to deserve promotion rather than penalty.
                # The boost is a log curve (diminishing returns for
                # extremely rare words) scaled by TWO convergence factors:
                #
                # 1. channel_factor = min(1.0, (n_channels - 1) / 5)
                #    Requires multiple channels to confirm the match.
                # 2. word_factor = min(1.0, (n_unique_words - 1) / 3)
                #    Requires multiple distinct words to be shared.
                #
                # The MINIMUM of these two factors is used, so both
                # conditions must be met for a large boost:
                #   - 1 word on 5 channels → min(0.8, 0) = 0 → no boost
                #   - 2 words on 3 channels → min(0.4, 0.33) = 0.33
                #   - 3 words on 6 channels → min(1.0, 0.67) = 0.67
                # This prevents single rare words (even genuinely rare
                # ones like "Erinys") from outranking multi-word allusions.
                n_for_boost = info["n_scoring_channels"]
                channel_factor = min(1.0, (n_for_boost - 1) / 5.0)
                word_factor = min(1.0, (n_unique_words - 1) / 3.0)
                boost_factor = min(channel_factor, word_factor)
                multiplier = min(_rarity_boost_cap,
                                 1.0 + _rarity_boost_weight * boost_factor * math.log(geom_mean_idf / _idf_threshold))

            # Min-IDF gate (currently disabled: threshold=0.0, penalty=1.0)
            if _min_idf_penalty < 1.0 and _min_idf_threshold > 0:
                if min(corpus_idfs) < _min_idf_threshold:
                    multiplier *= _min_idf_penalty
        else:
            # No corpus IDF data (all matched words had df=0 or idf=0):
            # neutral multiplier — don't penalize or boost
            multiplier = 1.0
            geom_mean_idf = 1.0

        # ---------------------------------------------------------------
        # LAYER 2: IDF-weighted convergence bonus
        # ---------------------------------------------------------------
        # Instead of counting each confirming channel as 1.0 toward
        # the convergence bonus, we weight each by min(1.0, geom_idf)^2.
        # The squaring makes the penalty much steeper for common words:
        #   geom_idf=0.36 ("tum vero")    → idf_weight=0.13
        #     6 channels * 0.13 = weighted_n=0.78 → no bonus (needs > 1.0)
        #   geom_idf=1.0+ ("centum angues") → idf_weight=1.0
        #     4 channels * 1.0 = weighted_n=4.0 → bonus = 0.75 * 3.0 = 2.25
        # This is the primary mechanism that eliminates convergence credit
        # for common-word pairs, even when they match on many channels.
        idf_weight = min(1.0, geom_mean_idf) ** 2
        base_score = info["score"]
        n = info["n_scoring_channels"]
        weighted_n = n * idf_weight
        conv_score = _convergence_bonus * (weighted_n - 1.0) if weighted_n > 1.0 else 0.0

        # ---------------------------------------------------------------
        # Final score assembly
        # ---------------------------------------------------------------
        # Layer 1 (penalty): base_score * mult^2
        #   The squaring makes the penalty much steeper: mult=0.5 → 0.25,
        #   mult=0.2 → 0.04. Rare words (mult=1.0) are unaffected.
        # Layer 2 (convergence): conv_score * mult^power
        #   The convergence bonus is also scaled by the rarity multiplier,
        #   but only to the first power (not squared), since the IDF
        #   weighting in weighted_n already provides steep suppression.
        conv_mult = multiplier ** _conv_idf_power
        info["score"] = base_score * (multiplier ** _penalty_power) + conv_score * conv_mult

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
            fused = fuse_results(line_channel_results, language=language)
            preview_cap = min(max_results, 500) if max_results > 0 else 500
            top = fused[:preview_cap]
            yield ("intermediate", {
                "results": top,
                "total_results": len(fused),
                "channels_done": list(line_channel_results.keys()),
                "phase": "line",
            })

    line_fused = fuse_results(line_channel_results, language=language)

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

    window_fused = fuse_results(window_channel_results, language=language)

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
    line_fused = fuse_results(line_channel_results, language=language)

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
    window_fused = fuse_results(window_channel_results, language=language)

    if mode == 'window':
        return window_fused[:max_results] if max_results > 0 else window_fused

    # --- Merge: line results first, then novel window results ---
    merged = merge_line_and_window(line_fused, window_fused)

    return merged[:max_results] if max_results > 0 else merged
