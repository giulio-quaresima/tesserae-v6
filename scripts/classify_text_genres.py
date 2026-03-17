#!/usr/bin/env python3
"""
Tesserae V6 — Auto-classify Latin texts by genre, era, and meter from filenames.

Reads all .tess filenames from texts/la/ and applies rule-based genre
classification, plus era lookup (from author_dates.json) and meter
detection (from mqdq_scansions.json + genre-based inference).

Outputs data/text_genres.csv for use by the admin panel
and (future) genre-specific IDF computation.

Usage:
    python scripts/classify_text_genres.py
"""

import csv
import json
import os
import re
import sys

# ─── Configuration ───────────────────────────────────────────────────────────

TEXTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'texts', 'la')
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), '..', 'data', 'text_genres.csv')
AUTHOR_DATES_PATH = os.path.join(os.path.dirname(__file__), '..', 'backend', 'author_dates.json')
SCANSION_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'scansion', 'mqdq_scansions.json')

# ─── Era lookup ──────────────────────────────────────────────────────────────

def _load_author_dates():
    """Load author_dates.json and return flat dict: author_key -> era string."""
    path = os.path.abspath(AUTHOR_DATES_PATH)
    if not os.path.exists(path):
        print(f"WARNING: author_dates.json not found at {path}")
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Flatten all languages into a single dict keyed by author name
    result = {}
    for lang_data in data.values():
        for author_key, info in lang_data.items():
            result[author_key.lower()] = info.get('era', 'Unknown')
    return result


def lookup_era(author, author_dates):
    """Look up era for an author. Tries exact match, then partial matches."""
    a = author.lower()
    # Exact match
    if a in author_dates:
        return author_dates[a]
    # Try without _pseudo suffix
    base = re.sub(r'_pseudo$', '', a)
    if base in author_dates:
        return author_dates[base]
    # Try the first part before _of_, _the_, _saint etc.
    simplified = re.split(r'_(of|the|saint|bishop|pseudo|active)', a)[0]
    if simplified in author_dates:
        return author_dates[simplified]
    return 'unknown'


# ─── Meter lookup (MQDQ scansion data) ──────────────────────────────────────

# Map MQDQ meter_type codes to human-readable labels
METER_TYPE_MAP = {
    'H': 'hexameter',
    'P': 'elegiac',       # pentameter (appears in elegiac couplets)
    'D': 'lyric',         # various lyric meters (Horace odes)
    'G': 'mixed',         # mixed meters
    'G1': 'lyric',        # iambic/epodic meters
    'F': 'mixed',         # mixed meters (polymetric books)
    'O': 'lyric',         # other lyric meters
    'X': 'hexameter',     # hexameter variant marking
    'Y': 'mixed',         # mixed minor meters
    'elegiac': 'elegiac',
    'hendecasyllable': 'lyric',
}

# Map scansion author names to .tess author names
SCANSION_AUTHOR_MAP = {
    'vergilius': 'vergil',
    'horatius': 'horace',
    'ouidius': 'ovid',
    'lucanus': 'lucan',
    'iuuenalis': 'juvenal',
    'iuuencus': 'juvencus',
    'martialis': 'martial',
}


def _load_scansion_data():
    """Load MQDQ scansion data and build a lookup dict.
    Returns dict: (normalized_author, normalized_work) -> meter label.
    Also returns a by-author dict for partial matching.
    """
    path = os.path.abspath(SCANSION_PATH)
    if not os.path.exists(path):
        print(f"WARNING: mqdq_scansions.json not found at {path}")
        return {}, {}

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    by_key = {}   # (author, work) -> meter
    by_author = {}  # author -> set of meters

    for key, info in data.items():
        raw_meter = info.get('meter_type', '')
        if not raw_meter:
            continue
        meter = METER_TYPE_MAP.get(raw_meter, raw_meter.lower())

        parts = key.split('.', 1)
        scansion_author = parts[0].lower()
        scansion_work = parts[1].lower() if len(parts) > 1 else ''

        # Normalize author name to match .tess conventions
        tess_author = SCANSION_AUTHOR_MAP.get(scansion_author, scansion_author)

        # Normalize work name: strip trailing _N (book numbers), lowercase
        # e.g., "Aeneis" -> "aeneis", "siluae_1" -> "siluae"
        tess_work = scansion_work.lower()
        # Remove .part.N suffixes
        tess_work = re.sub(r'\.part\.\d+.*$', '', tess_work)

        by_key[(tess_author, tess_work)] = meter

        if tess_author not in by_author:
            by_author[tess_author] = set()
        by_author[tess_author].add(meter)

    return by_key, by_author


# Genre -> default meter mapping (for texts not in scansion data)
GENRE_METER_MAP = {
    'epic': 'hexameter',
    'pastoral': 'hexameter',
    'panegyric': 'hexameter',
    'elegy': 'elegiac',
    'lyric': 'lyric',
    'satire': 'hexameter',       # Horace/Juvenal/Persius are hex satirists
    'drama': 'dramatic',
    'oratory': 'prose',
    'philosophy': 'prose',
    'historiography': 'prose',
    'epistolary': 'prose',
    'technical': 'prose',
    'theology': 'prose',
    'rhetoric': 'prose',
    'scripture': 'prose',
    'medieval': 'unknown',        # could be verse or prose
    'christian_poetry': 'unknown',  # varies
    'unclassified': 'unknown',
}

# Work name aliases to help match scansion data to .tess filenames
WORK_ALIASES = {
    # vergil
    ('vergil', 'aeneid'): [('vergil', 'aeneis'), ('vergilius', 'aeneis')],
    ('vergil', 'eclogues'): [('vergil', 'eclogae'), ('vergilius', 'eclogae')],
    ('vergil', 'georgics'): [('vergil', 'georgicon'), ('vergilius', 'georgicon')],
    # ovid
    ('ovid', 'ex_ponto'): [('ovid', 'ex_ponto_1'), ('ovid', 'ex_ponto_2'),
                            ('ovid', 'ex_ponto_3'), ('ovid', 'ex_ponto_4'),
                            ('ouidius', 'ex_ponto_1')],
    ('ovid', 'tristia'): [('ovid', 'tristia_1'), ('ovid', 'tristia_3'),
                           ('ovid', 'tristia_4'), ('ovid', 'tristia_5'),
                           ('ouidius', 'tristia_1')],
    ('ovid', 'amores'): [('ovid', 'amores'), ('ouidius', 'amores_1')],
    ('ovid', 'ars_amatoria'): [('ovid', 'ars_amatoria'), ('ouidius', 'ars')],
    ('ovid', 'heroides'): [('ovid', 'heroides'), ('ouidius', 'epistulae_heroides')],
    ('ovid', 'fasti'): [('ovid', 'fasti'), ('ouidius', 'fasti')],
    ('ovid', 'metamorphoses'): [('ovid', 'metamorphoses'), ('ouidius', 'metamorphoses')],
    # horace
    ('horace', 'satires'): [('horace', 'saturae_1'), ('horace', 'saturae_2'),
                             ('horatius', 'saturae_1'), ('horatius', 'saturae_2')],
    ('horace', 'epistles'): [('horace', 'epistulae_1'), ('horace', 'epistulae_2'),
                              ('horatius', 'epistulae_1'), ('horatius', 'epistulae_2')],
    ('horace', 'odes'): [('horace', 'carmina_1'), ('horace', 'carmina_4'),
                          ('horatius', 'carmina_1'), ('horatius', 'carmina_4')],
    ('horace', 'epodes'): [('horace', 'epodi'), ('horatius', 'epodi')],
    # statius
    ('statius', 'thebaid'): [('statius', 'thebais')],
    ('statius', 'achilleid'): [('statius', 'achilleis')],
    ('statius', 'silvae'): [('statius', 'siluae_1'), ('statius', 'siluae_2'),
                             ('statius', 'siluae_3'), ('statius', 'siluae_4'),
                             ('statius', 'siluae_5')],
    # lucan
    ('lucan', 'bellum_civile'): [('lucan', 'pharsalia'), ('lucanus', 'pharsalia')],
    # silius
    ('silius_italicus', 'punica'): [('silius_italicus', 'punica')],
    # valerius flaccus
    ('valerius_flaccus', 'argonautica'): [('valerius_flaccus', 'argonautica')],
    # propertius
    ('propertius', 'elegiae'): [('propertius', 'elegiae_1'), ('propertius', 'elegiae_2'),
                                 ('propertius', 'elegiae_3'), ('propertius', 'elegiae_4'),
                                 ('propertius', 'elegies')],
    # tibullus
    ('tibullus', 'elegiae'): [('tibullus', 'elegiae_1'), ('tibullus', 'elegiae_2'),
                               ('tibullus', 'elegies')],
    # juvenal
    ('juvenal', 'saturae'): [('juvenal', 'saturae'), ('iuuenalis', 'saturae')],
    # persius
    ('persius', 'saturae'): [('persius', 'saturae')],
    # catullus
    ('catullus', 'carmina'): [('catullus', 'carmina')],
    # martial
    ('martial', 'epigrams'): [('martial', 'epigrams')],
    # seneca
    ('seneca', 'apocolocyntosis'): [('seneca', 'apocolocyntosis')],
    # claudian
    ('claudian', 'de_raptu_proserpinae'): [('claudianus', 'de_raptu_proserpinae')],
    # calpurnius
    ('calpurnius_siculus', 'eclogae'): [('calpurnius_siculus', 'eclogae')],
}


def lookup_meter(author, work, genre, scansion_keys, scansion_by_author, text_type_func=None, filename=None):
    """Determine meter for a text using scansion data + genre inference.

    Priority:
    1. Exact (author, work) match in scansion data
    2. Alias-based match
    3. If text_type is prose -> 'prose'
    4. Genre-based inference
    """
    a = author.lower()
    w = work.lower() if work else ''

    # 1. Exact match
    if (a, w) in scansion_keys:
        return scansion_keys[(a, w)]

    # Try with numbered suffix stripped (e.g., silvae -> siluae_1)
    # and case variations
    for key, meter in scansion_keys.items():
        ka, kw = key
        # Match if tess author matches and work is a prefix
        if ka == a and kw.startswith(w) and w:
            return meter
        # Match with work name starting with our work
        if ka == a and w and w.startswith(kw):
            return meter

    # 2. Check aliases
    alias_key = (a, w)
    if alias_key in WORK_ALIASES:
        for alt_a, alt_w in WORK_ALIASES[alias_key]:
            alt_a = alt_a.lower()
            alt_w = alt_w.lower()
            if (alt_a, alt_w) in scansion_keys:
                return scansion_keys[(alt_a, alt_w)]

    # 3. Check text_type (prose override)
    if text_type_func and filename:
        try:
            text_type = text_type_func(filename)
            if text_type == 'prose':
                return 'prose'
        except Exception:
            pass

    # 4. Genre-based inference
    return GENRE_METER_MAP.get(genre, 'unknown')

# Genre definitions: each entry is (genre_name, list_of_matching_rules)
# Rules are checked in order; first match wins.
# A rule is a tuple of (author_pattern, work_pattern) where patterns are
# compiled regexes matched against the extracted author and work name.
# Use None to match any value.

# Helper to build rules concisely
def _author(pattern):
    """Match author name (case-insensitive partial match)."""
    return re.compile(pattern, re.IGNORECASE)

def _work(pattern):
    """Match work name (case-insensitive partial match)."""
    return re.compile(pattern, re.IGNORECASE)


# ─── Seneca tragedy titles (distinct from philosophical prose) ───────────────
SENECA_TRAGEDIES = {
    'agamemnon', 'hercules_furens', 'hercules_oetaeus', 'medea',
    'octavia', 'oedipus', 'phaedra', 'phoenissae', 'thyestes', 'troades'
}

# ─── Cicero speeches (oratory) ──────────────────────────────────────────────
CICERO_SPEECHES_PATTERNS = [
    r'pro_', r'in_catilinam', r'in_l_pisonem', r'in_vatinium',
    r'philippicae', r'de_imperio', r'de_lege_agraria', r'de_domo_sua',
    r'de_haruspicum', r'de_provinciis', r'post_reditum', r'cum_populo',
    r'divinatio_in_', r'pro_archia', r'de_optimo_genere_oratorum',
]

# ─── Cicero rhetorical theory ───────────────────────────────────────────────
CICERO_RHETORIC_PATTERNS = [
    r'de_inventione', r'de_oratore', r'de_partitione', r'orator$',
    r'brutus', r'topica',
]

# ─── Classification rules ───────────────────────────────────────────────────

def classify_text(author, work, filename):
    """
    Classify a single text by genre based on author and work name.
    Returns (genre, confidence) where confidence is 'auto'.
    """
    a = author.lower()
    w = work.lower() if work else ''

    # ── Epic ─────────────────────────────────────────────────────────────
    if a == 'vergil' and w in ('aeneid', 'georgics'):
        return 'epic'
    if a == 'lucan' and 'bellum_civile' in w:
        return 'epic'
    if a in ('statius',) and w in ('thebaid', 'achilleid'):
        return 'epic'
    if a == 'valerius_flaccus' and 'argonautica' in w:
        return 'epic'
    if a == 'silius_italicus' and 'punica' in w:
        return 'epic'
    if a == 'ovid' and w == 'metamorphoses':
        return 'epic'
    if a == 'ennius' and 'annales' in w:
        return 'epic'
    if a == 'claudian' and 'de_raptu_proserpinae' in w:
        return 'epic'
    if a == 'lucretius' and 'de_rerum_natura' in w:
        return 'epic'  # didactic epic
    if a == 'manilius' and w in ('astronomica', 'astronomicon'):
        return 'epic'  # didactic epic
    if a == 'corippus' and 'johannis' in w:
        return 'epic'
    if a == 'maffeo_veggio' and 'aeneid' in w:
        return 'epic'  # Aeneid continuation
    if a == 'italicus':
        return 'epic'
    # Late antique biblical epic
    if a in ('iuuencus', 'juvencus', 'juvencus_caius_vettius_aquilinus'):
        return 'epic'
    if a == 'cyprianus_gallus' and 'heptateuchos' in w:
        return 'epic'
    if a == 'sedulius' and 'carmen_paschale' in w:
        return 'epic'
    if a == 'avitus_of_vienne' and 'spiritalis' in w:
        return 'epic'
    if a == 'dracontius' and 'de_laudibus_dei' in w:
        return 'epic'
    if a == 'victor_claudius_marius' and ('alethia' in w or 'genesim' in w):
        return 'epic'
    if a == 'proba_active_4th_century' and 'cento' in w:
        return 'epic'  # Virgilian cento
    if a == 'paulinus_petricordiae':
        return 'epic'  # versified hagiography
    if a == 'ermoldus_nigellus':
        return 'epic'  # Carolingian panegyric epic
    if a == 'poeta_saxo':
        return 'epic'  # Carolingian versified history
    if a == 'walafrid_strabo' and 'visio_wettini' in w:
        return 'epic'  # verse narrative
    if a == 'karolus_magnus_et_leo_papa' in filename.lower():
        return 'epic'

    # ── Elegy ────────────────────────────────────────────────────────────
    if a == 'ovid' and w in ('amores', 'tristia', 'ex_ponto', 'fasti',
                              'heroides', 'ars_amatoria', 'remedia_amoris',
                              'medicamina_faciei_femineae', 'ibis'):
        return 'elegy'
    if 'ovid' in a and 'heroides' in w:
        return 'elegy'
    if a == 'tibullus':
        return 'elegy'
    if a == 'propertius':
        return 'elegy'
    if a == 'maximianus':
        return 'elegy'
    if a == 'rutilius':
        return 'elegy'  # Rutilius Namatianus, elegiac travel poem

    # ── Lyric ────────────────────────────────────────────────────────────
    if a == 'catullus':
        return 'lyric'  # mixed meters, primarily lyric collection
    if a == 'horace' and w in ('odes', 'carmen_saeculare', 'epodes'):
        return 'lyric'
    if a == 'statius' and w == 'silvae':
        return 'lyric'  # occasional poetry, mixed meters

    # ── Satire / Epigram ─────────────────────────────────────────────────
    if a == 'horace' and w in ('satires', 'ars_poetica', 'epistles'):
        return 'satire'  # sermones tradition
    if a == 'juvenal':
        return 'satire'
    if a == 'persius':
        return 'satire'
    if a in ('martial', 'martialis'):
        return 'satire'  # epigram, satirical tradition
    if a == 'petronius':
        return 'satire'  # Menippean satire / novel
    if a == 'apuleius' and w in ('metamorphoses', 'florida'):
        return 'satire'  # novel / Menippean tradition
    if a == 'seneca' and w == 'apocolocyntosis':
        return 'satire'  # Menippean satire
    if a == 'phaedrus':
        return 'satire'  # fables, satirical tradition

    # ── Drama ────────────────────────────────────────────────────────────
    if a == 'plautus':
        return 'drama'
    if a == 'terence':
        return 'drama'
    if a == 'seneca' and w in SENECA_TRAGEDIES:
        return 'drama'
    if a == 'dracontius' and w == 'orestes':
        return 'drama'

    # ── Oratory ──────────────────────────────────────────────────────────
    if a == 'cicero':
        for pat in CICERO_SPEECHES_PATTERNS:
            if re.search(pat, w):
                return 'oratory'
    if a == 'cicero_pseudo' and ('in_sallustium' in w or 'exilium' in w):
        return 'oratory'
    if a == 'seneca_the_elder':
        return 'oratory'  # declamation
    if a == 'quintilian' and 'institutio' in w:
        return 'oratory'  # rhetorical education
    if a == 'quintilian_pseudo' and 'declamation' in w:
        return 'oratory'
    if a == 'claudius_mamertinus':
        return 'oratory'  # panegyric

    # ── Rhetoric ─────────────────────────────────────────────────────────
    if a == 'cicero':
        for pat in CICERO_RHETORIC_PATTERNS:
            if re.search(pat, w):
                return 'rhetoric'

    # ── Philosophy ───────────────────────────────────────────────────────
    if a == 'cicero' and w in ('academica', 'lucullus', 'de_natura_deorum',
                                'de_divinatione', 'de_fato', 'de_republica',
                                'de_finibus_bonorum_et_malorum',
                                'tusculanae_disputationes', 'de_officiis',
                                'de_amicitia', 'de_senectute',
                                'paradoxa_stoicorum_ad_m_brutum', 'timaeus'):
        return 'philosophy'
    if a == 'seneca' and w in ('ad_lucilium_epistulae_morales',
                                'de_beneficiis', 'de_brevitate_vitae',
                                'de_clementia', 'de_consolatione_ad_helviam',
                                'de_consolatione_ad_marciam',
                                'de_consolatione_ad_polybium',
                                'de_constantia', 'de_ira', 'de_otio',
                                'de_providentia', 'de_tranquillitate_animi',
                                'de_vita_beata', 'quaestiones_naturales'):
        return 'philosophy'
    if a == 'boethius' and ('consolatio' in w or 'de_consolatione' in w):
        return 'philosophy'
    if a == 'boethius' and ('fide' in w or 'trinitas' in w or 'persona' in w
                            or 'substantiae' in w or 'utrum' in w
                            or 'porphyrium' in w):
        return 'philosophy'  # theological/philosophical treatises
    if a == 'apuleius' and w in ('apologia', 'de_deo_socratis'):
        return 'philosophy'
    if a == 'macrobius':
        return 'philosophy'  # Saturnalia, commentary
    if a == 'favonius':
        return 'philosophy'
    if a == 'gellius':
        return 'philosophy'  # miscellany, intellectual culture
    if a == 'claudianus_mamertus' and 'de_statu_animae' in w:
        return 'philosophy'

    # ── Historiography ───────────────────────────────────────────────────
    if a == 'caesar' or a == 'caesar_augustus':
        return 'historiography'
    if a == 'livy':
        return 'historiography'
    if a == 'sallust':
        return 'historiography'
    if a == 'tacitus' and w in ('annales', 'historiae', 'agricola',
                                 'de_origine_et_situ_germanorum_liber'):
        return 'historiography'
    if a == 'tacitus' and 'dialogus' in w:
        return 'rhetoric'  # Dialogus de oratoribus
    if a == 'suetonius':
        return 'historiography'
    if a == 'curtius_rufus':
        return 'historiography'
    if a == 'nepos':
        return 'historiography'  # biography
    if a == 'ammianus':
        return 'historiography'
    if a == 'eutropius':
        return 'historiography'
    if a == 'florus' or a == 'florus_of_lyon':
        return 'historiography'
    if a == 'aurelius_victor':
        return 'historiography'
    if a == 'valerius_maximus':
        return 'historiography'  # exempla collection
    if a == 'scriptores_historiae_augustae':
        return 'historiography'
    if a in ('orosius_paulus', 'paulus_orosius') and 'historiae' in w:
        return 'historiography'
    if a == 'flavius_josephus':
        return 'historiography'
    if a in ('hegesippus_pseudo',):
        return 'historiography'
    if a == 'william_of_tyre':
        return 'historiography'
    if a == 'fulcher_of_chartres':
        return 'historiography'
    if a == 'nithardus':
        return 'historiography'
    if a == 'einhardus':
        return 'historiography'  # Vita Karoli
    if a == 'erchempert':
        return 'historiography'
    if a == 'agnellus_ravennatis':
        return 'historiography'
    if a == 'rufius_festus':
        return 'historiography'  # Breviarium

    # ── Epistolary ───────────────────────────────────────────────────────
    if a == 'cicero' and ('epistulae' in w or 'letters' in w):
        return 'epistolary'
    if a == 'q_cicero':
        return 'epistolary'
    if a == 'pliny_the_younger' and 'letters' in w:
        return 'epistolary'
    if a in ('jerome', 'jerome_saint') and 'epistulae' in w:
        return 'epistolary'
    if a == 'paulinus_of_nola' and 'epistulae' in w:
        return 'epistolary'
    if a == 'ambrose' and ('epistul' in w):
        return 'epistolary'
    if a == 'augustine' and ('epistul' in w):
        return 'epistolary'
    if a == 'cyprian' and 'epistul' in w:
        return 'epistolary'
    if a == 'cyprian_saint' and 'epistul' in w:
        return 'epistolary'
    if a == 'cyprian_pseudo' and 'epistul' in w:
        return 'epistolary'
    if a == 'claudianus_mamertus' and 'epistol' in w:
        return 'epistolary'
    if a == 'sulpicius_severus' and 'epistul' in w:
        return 'epistolary'
    if a == 'sulpicius_severus_pseudo':
        return 'epistolary'
    if a == 'faustus_of_riez' and 'epistul' in w:
        return 'epistolary'
    if a == 'salvian_of_marseilles' and 'epistul' in w:
        return 'epistolary'
    if a == 'salvianus' and 'epistul' in w:
        return 'epistolary'
    if a == 'lupus_servatus':
        return 'epistolary'
    if a == 'ruricius_i_bishop_of_limoges':
        return 'epistolary'

    # ── Technical / encyclopedic ─────────────────────────────────────────
    if a == 'pliny_the_elder':
        return 'technical'
    if a == 'columella':
        return 'technical'  # agriculture
    if a == 'vitruvius':
        return 'technical'  # architecture
    if a == 'celsus':
        return 'technical'  # medicine
    if a == 'cato_the_elder':
        return 'technical'  # agriculture
    if a == 'priscian':
        return 'technical'  # grammar
    if a == 'servius_honoratus':
        return 'technical'  # commentary
    if a == 'lactantius_placidus':
        return 'technical'  # commentary on Statius

    # ── Pastoral / Bucolic ───────────────────────────────────────────────
    if a == 'vergil' and w == 'eclogues':
        return 'pastoral'
    if a == 'calpurnius_siculus' and 'eclog' in w:
        return 'pastoral'

    # ── Christian prose (theology, apologetics, exegesis) ────────────────
    if a in ('augustine', 'augustine_pseudo'):
        return 'theology'  # default for Augustine
    if a in ('ambrose',):
        return 'theology'
    if a in ('tertullian', 'tertullian_pseudo'):
        return 'theology'
    if a in ('cyprian', 'cyprian_saint', 'cyprian_pseudo',
             'pseudo_cyprian'):
        return 'theology'
    if a in ('lactantius',):
        return 'theology'
    if a in ('hilary_of_poitiers', 'hilary_of_poitiers_pseudo',
             'hilary_saint_archbishop_of_arles',
             'hilary_saint_bishop_of_poitiers'):
        return 'theology'
    if a in ('jerome', 'jerome_saint') and 'vulgate' in w:
        return 'scripture'  # Bible translation
    if a in ('jerome', 'jerome_saint'):
        return 'theology'
    if a in ('arnobius', 'arnobius_advesus_nationes', 'arnobius_of_sicca'):
        return 'theology'
    if a in ('minucius_felix', 'marcus_mincuius_felix'):
        return 'theology'
    if a in ('john_cassian',):
        return 'theology'
    if a in ('eucherius_of_lyon',):
        return 'theology'
    if a in ('faustus_of_riez',):
        return 'theology'
    if a in ('optatus_saint_bishop_of_mileve',):
        return 'theology'
    if a in ('salvian_of_marseilles', 'salvianus'):
        return 'theology'
    if a in ('orosius_paulus', 'paulus_orosius'):
        return 'theology'  # apologetic history
    if a in ('rufinus', 'rufinus_of_aquileia'):
        return 'theology'
    if a in ('evagrius_monachus',):
        return 'theology'
    if a in ('lucifer_bishop_of_cagliari',):
        return 'theology'
    if a in ('philastrius',):
        return 'theology'
    if a in ('priscillian', 'priscillian_bishop_of_avila'):
        return 'theology'
    if a in ('iulius_firmicus_maternus', 'julius_firmicus_maternus'):
        return 'theology'
    if a == 'paul_the_apostle_saint':
        return 'theology'
    if a in ('evodius', 'evodius_bishop_of_uzalis'):
        return 'theology'
    if a == 'pontius_diaconus':
        return 'theology'  # hagiography
    if a in ('victor_vitensis', 'vitensis', 'vitensis_pseudo',
             'pseudo_victor_vitensis'):
        return 'theology'  # persecution history
    if a == 'eugippius':
        return 'theology'
    if a in ('pseudo_eucherius',):
        return 'theology'
    if a in ('pseudo_severus_sulpicius',):
        return 'theology'
    if a in ('pseudo_tertullian',):
        return 'theology'
    if a == 'sulpicius_severus':
        return 'theology'  # hagiography (Vita Martini, Chronica)
    if a == 'victorinus' or a == 'victorinus_saint_bishop_of_poetovio':
        return 'theology'
    if a == 'rusticus_presbyter':
        return 'theology'
    if a == 'commodian' or a == 'commodianus':
        return 'theology'  # Christian didactic verse

    # ── Carolingian / Medieval poetry ────────────────────────────────────
    # These are harder to classify neatly. Many are "carmina" or occasional verse.
    CAROLINGIAN_AUTHORS = {
        'alcuin', 'hrabanus', 'theodulf_of_orleans', 'thedulf_of_orleans',
        'walafrid_strabo', 'walahfrid_strabo', 'sedulius_scotus',
        'paulus_diaconus', 'petrus_of_pisa', 'paulinus_of_aquileia',
        'audradus_modicus', 'moduin', 'candidus_of_fulda',
        'micon_of_saint_riquier', 'milo_of_saint_amand',
        'hincmar', 'john_scotus_eriugena', 'smaragdus',
        'wandalbert', 'wandalbertus', 'fardulfus', 'engelmodus',
        'hibernicus_exul', 'godescalcus_saxus', 'sigloardus_remensis',
        'bernowinus', 'gerwardus', 'petrus_diaconus',
        'agius_of_corvey', 'bertharius_of_monte_cassino',
        'ermenricus_elwagensis', 'cyprianus_cordubensis',
        'johannes_hymonides', 'angilbert_carmina', 'angilbertus_miles',
        'angilbert_versus', 'remigius_of_auxerre', 'paulus_albarus',
        'lios_monocus', 'vulfinus_diensis', 'paschasius_radbertus',
        'florus_of_lyon', 'giraldus_floriacensis',
        'aimoin_of_saint_germain', 'amalarius',
    }
    if a in CAROLINGIAN_AUTHORS:
        return 'medieval'

    # Bede
    if a in ('bede', 'bede_the_venerable'):
        return 'medieval'

    # Medieval misc
    if a in ('hildebert_of_lavardin', 'marbodus_redonensis',
             'petrus_riga', 'giovanni_aurelio_augurelli'):
        return 'medieval'
    if a in ('dhuoda',):
        return 'medieval'

    # ── Christian verse (not Carolingian, not biblical epic) ─────────────
    if a == 'prudentius':
        return 'christian_poetry'
    if a == 'paulinus_of_nola' and 'carmina' in w:
        return 'christian_poetry'
    if a == 'paulinus_of_pella':
        return 'christian_poetry'
    if a == 'orientius_saint':
        return 'christian_poetry'
    if a == 'sedulius' and w != 'carmen_paschale':
        return 'christian_poetry'

    # ── Late antique panegyric / political verse ─────────────────────────
    if a == 'claudian' and w != 'de_raptu_proserpinae':
        return 'panegyric'

    # ── Misc prose genres ────────────────────────────────────────────────
    if a == 'seneca' and 'carminum_fragmenta' in w:
        return 'lyric'  # fragments of verse

    # ── Vergil pseudo / appendix ─────────────────────────────────────────
    if a == 'vergil_pseudo':
        if w in ('aetna', 'culex', 'ciris', 'dirae'):
            return 'epic'  # minor epic / epyllion
        if w in ('catalepton', 'priapea', 'copa', 'moretum', 'lydia'):
            return 'lyric'  # minor verse
        if 'appendix' in w or 'elegiae' in w:
            return 'elegy'
        return 'lyric'

    # ── Dracontius remaining ─────────────────────────────────────────────
    if a == 'dracontius':
        return 'lyric'  # Romulea = occasional poetry

    # ── Prose misc ───────────────────────────────────────────────────────
    if a == 'seneca':
        return 'philosophy'  # catch-all for remaining Seneca

    # ── Travel / pilgrimage ──────────────────────────────────────────────
    if 'itinerarium' in w or 'peregrinatio' in w or 'pilgrim' in a:
        return 'technical'  # travel writing
    if a in ('adamnan', 'theodosius') and ('locis' in w or 'terrae' in w):
        return 'technical'  # pilgrim guides

    # ── Anonymous texts ──────────────────────────────────────────────────
    if a in ('anonymi', 'anonymous', 'anonymus'):
        # Try to classify by work title
        if 'carmen' in w or 'carmina' in w or 'versus' in w or 'hymnus' in w:
            return 'medieval'  # default for anonymous verse
        if 'planctus' in w or 'laudes' in w:
            return 'medieval'
        if 'translatio' in w:
            return 'medieval'  # hagiographic
        if 'itinerarium' in w or 'breviarius' in w:
            return 'technical'
        if 'karolus' in w or 'tituli' in w:
            return 'medieval'
        return 'unclassified'

    # ── Ambrosiaster ─────────────────────────────────────────────────────
    if a == 'ambrosiaster':
        return 'theology'

    # ── Ennodius (Magnus Felix) ──────────────────────────────────────────
    if a in ('ennodius', 'magnus_felix_ennodius'):
        return 'medieval'  # late antique / early medieval

    # ── Eobanus ──────────────────────────────────────────────────────────
    if a == 'eobanus':
        return 'medieval'  # Renaissance humanist

    # ── Polignac ─────────────────────────────────────────────────────────
    if a == 'polignac':
        return 'philosophy'  # Anti-Lucretius

    # ── Dante, Descartes ─────────────────────────────────────────────────
    if a == 'dante':
        return 'epic'  # Latin works
    if a == 'descartes':
        return 'philosophy'

    # ── Salutati ─────────────────────────────────────────────────────────
    if a == 'salutati':
        return 'epistolary'  # humanist letters

    # ── Catholic Church / papal ──────────────────────────────────────────
    if a == 'catholic_church_pope':
        return 'theology'

    # ── Aethelwulf ───────────────────────────────────────────────────────
    if a == 'aethelwulf':
        return 'medieval'

    # ── Glass ────────────────────────────────────────────────────────────
    if a == 'glass':
        return 'unclassified'

    # ── Couplet ──────────────────────────────────────────────────────────
    if a == 'couplet_et_alii':
        return 'unclassified'

    # ── Unknown ──────────────────────────────────────────────────────────
    if a == 'unknown':
        return 'unclassified'

    # ── Optatian ─────────────────────────────────────────────────────────
    if a == 'optatian':
        return 'panegyric'  # pattern poetry for Constantine

    # ── Secundinus ───────────────────────────────────────────────────────
    if a in ('secundinus', 'secundinus_manichaeus'):
        return 'theology'

    # ── Corippus ─────────────────────────────────────────────────────────
    if a == 'corippus':
        return 'panegyric'  # In laudem Iustini

    # ── Ausonius (late antique polymath, mixed genres) ──────────────────
    if a == 'ausonius':
        if 'epistul' in w:
            return 'epistolary'
        if 'gratiarum' in w or 'oratio' in w:
            return 'oratory'
        if 'mosella' in w:
            return 'epic'  # descriptive hexameter poem
        if 'cento' in w:
            return 'epic'  # Virgilian cento
        # Default: miscellaneous verse (epigrammata, parentalia, etc.)
        return 'lyric'

    # ── Severus Sulpicius (= Sulpicius Severus duplicate) ───────────────
    if a == 'severus_sulpicius':
        if 'epistul' in w:
            return 'epistolary'
        return 'theology'  # Chronica, Dialogi, Vita Martini

    # ── Avitus remaining ─────────────────────────────────────────────────
    if a == 'avitus_of_vienne':
        return 'christian_poetry'

    # ── Dicuil ───────────────────────────────────────────────────────────
    if a == 'dicuil':
        return 'medieval'

    # ── Aristotle (Latin translation) ────────────────────────────────────
    if a == 'aristotle':
        return 'philosophy'

    # ── Default ──────────────────────────────────────────────────────────
    return 'unclassified'


def parse_filename(filename):
    """
    Extract author and work from a .tess filename.
    Returns (author, work) tuple.

    Examples:
        vergil.aeneid.part.1.tess -> ('vergil', 'aeneid')
        cicero.pro_milone.tess -> ('cicero', 'pro_milone')
        alcuin.carmina.part.102.tess -> ('alcuin', 'carmina')
    """
    # Remove .tess extension
    name = filename.replace('.tess', '').replace('.tess.bak', '')

    # Remove .part.N suffix
    name = re.sub(r'\.part\.\d+[^.]*$', '', name)
    # Also handle .part.N.description suffixes
    name = re.sub(r'\.part\.\d+\..*$', '', name)

    # Split on first dot to get author.work
    parts = name.split('.', 1)
    author = parts[0]
    work = parts[1] if len(parts) > 1 else ''

    return author, work


def main():
    # Resolve paths
    texts_dir = os.path.abspath(TEXTS_DIR)
    output_csv = os.path.abspath(OUTPUT_CSV)

    if not os.path.isdir(texts_dir):
        print(f"ERROR: texts directory not found: {texts_dir}")
        sys.exit(1)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    # Load era and meter data
    author_dates = _load_author_dates()
    print(f"Loaded {len(author_dates)} author era entries")

    scansion_keys, scansion_by_author = _load_scansion_data()
    print(f"Loaded {len(scansion_keys)} scansion entries")

    # Try to import detect_text_type for prose override
    text_type_func = None
    try:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        from backend.utils import detect_text_type
        text_type_func = detect_text_type
        print("Loaded detect_text_type from backend.utils")
    except ImportError as e:
        print(f"WARNING: Could not import detect_text_type: {e}")

    # Read all .tess files
    files = sorted([f for f in os.listdir(texts_dir) if f.endswith('.tess')])
    print(f"Found {len(files)} .tess files in {texts_dir}")

    # Classify each file
    results = []
    genre_counts = {}
    era_counts = {}
    meter_counts = {}

    for filename in files:
        author, work = parse_filename(filename)
        genre = classify_text(author, work, filename)
        era = lookup_era(author, author_dates)
        meter = lookup_meter(author, work, genre, scansion_keys, scansion_by_author,
                             text_type_func, filename)

        results.append({
            'filename': filename,
            'author': author,
            'work': work,
            'era': era,
            'meter': meter,
            'genre': genre,
            'confidence': 'auto'
        })

        genre_counts[genre] = genre_counts.get(genre, 0) + 1
        era_counts[era] = era_counts.get(era, 0) + 1
        meter_counts[meter] = meter_counts.get(meter, 0) + 1

    # Write CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['filename', 'author', 'work', 'era', 'meter', 'genre', 'confidence'])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nWrote {len(results)} entries to {output_csv}")

    # Print genre summary
    print(f"\n{'Genre':<25} {'Count':>6} {'%':>7}")
    print('-' * 40)
    for genre, count in sorted(genre_counts.items(), key=lambda x: -x[1]):
        pct = count / len(results) * 100
        print(f"  {genre:<23} {count:>6} {pct:>6.1f}%")
    print('-' * 40)
    print(f"  {'TOTAL':<23} {len(results):>6}")

    classified = sum(c for g, c in genre_counts.items() if g != 'unclassified')
    unclassified = genre_counts.get('unclassified', 0)
    print(f"\n  Classified: {classified} ({classified/len(results)*100:.1f}%)")
    print(f"  Unclassified: {unclassified} ({unclassified/len(results)*100:.1f}%)")

    # Print era summary
    print(f"\n{'Era':<25} {'Count':>6} {'%':>7}")
    print('-' * 40)
    for era, count in sorted(era_counts.items(), key=lambda x: -x[1]):
        pct = count / len(results) * 100
        print(f"  {era:<23} {count:>6} {pct:>6.1f}%")

    # Print meter summary
    print(f"\n{'Meter':<25} {'Count':>6} {'%':>7}")
    print('-' * 40)
    for meter, count in sorted(meter_counts.items(), key=lambda x: -x[1]):
        pct = count / len(results) * 100
        print(f"  {meter:<23} {count:>6} {pct:>6.1f}%")

    # Print unique author.work combos that are unclassified
    if unclassified > 0:
        print(f"\nUnclassified texts:")
        seen = set()
        for r in results:
            if r['genre'] == 'unclassified':
                key = f"{r['author']}.{r['work']}"
                if key not in seen:
                    seen.add(key)
                    print(f"  {r['filename']}")


if __name__ == '__main__':
    main()
