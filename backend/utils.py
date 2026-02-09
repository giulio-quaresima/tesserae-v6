"""
Tesserae V6 - Utility Functions
"""
import os
import re
import json
import logging

logger = logging.getLogger(__name__)

OVERRIDES_PATH = os.path.join(os.path.dirname(__file__), 'text_metadata_overrides.json')
_overrides_cache = None
_overrides_mtime = 0

def load_metadata_overrides(force_reload=False):
    global _overrides_cache, _overrides_mtime
    try:
        mtime = os.path.getmtime(OVERRIDES_PATH)
        if not force_reload and _overrides_cache is not None and mtime == _overrides_mtime:
            return _overrides_cache
        with open(OVERRIDES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _overrides_cache = {k: v for k, v in data.items() if not k.startswith('_')}
        _overrides_mtime = mtime
        return _overrides_cache
    except Exception as e:
        logger.warning(f"Could not load metadata overrides: {e}")
        return {}

def save_metadata_overrides(overrides):
    global _overrides_cache, _overrides_mtime
    try:
        with open(OVERRIDES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
    meta_keys = {k: v for k, v in data.items() if k.startswith('_')}
    meta_keys['_last_updated'] = __import__('datetime').date.today().isoformat()
    merged = {**meta_keys, **overrides}
    with open(OVERRIDES_PATH, 'w', encoding='utf-8') as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    _overrides_cache = overrides
    _overrides_mtime = os.path.getmtime(OVERRIDES_PATH)

def get_override(text_id):
    overrides = load_metadata_overrides()
    return overrides.get(text_id, {})

def set_override(text_id, fields):
    overrides = load_metadata_overrides()
    if not fields or all(v == '' or v is None for v in fields.values()):
        overrides.pop(text_id, None)
    else:
        clean = {k: v for k, v in fields.items() if v is not None and v != ''}
        if clean:
            overrides[text_id] = clean
        else:
            overrides.pop(text_id, None)
    save_metadata_overrides(overrides)

def load_corpus(directory):
    """Load all .tess files from a directory"""
    texts = []
    if not os.path.exists(directory):
        return texts
    
    for filename in os.listdir(directory):
        if filename.endswith('.tess'):
            filepath = os.path.join(directory, filename)
            metadata = get_text_metadata(filepath)
            texts.append(metadata)
    
    return texts

def clean_cts_reference(ref):
    """Clean CTS URN references to extract readable locus
    e.g., 'urn:cts:latinLit:stoa0040.stoa001.opp-lat1.1.1' -> '1.1'
    """
    if not ref:
        return ref
    
    if 'urn:cts:' in ref:
        parts = ref.split('.')
        numeric_parts = []
        for p in reversed(parts):
            if p and (p.isdigit() or re.match(r'^\d+[a-z]?$', p)):
                numeric_parts.insert(0, p)
            else:
                break
        if numeric_parts:
            return '.'.join(numeric_parts)
    
    return ref

PROSE_WORKS = [
    'epistulae_ad_familiares', 'epistulae_ad_atticum', 'epistulae_morales',
    'letters_to_atticus', 'letters_to_brutus', 'letters_to_quintus', 'letters_to_friends',
    'de_oratore', 'de_officiis', 'de_finibus', 'de_natura_deorum',
    'de_republica', 'de_legibus', 'de_amicitia', 'de_senectute',
    'tusculanae', 'academica', 'brutus', 'orator',
    'pro_milone', 'pro_caelio', 'pro_murena', 'pro_archia', 'pro_sestio',
    'in_catilinam', 'in_verrem', 'philippicae',
    'bellum_gallicum', 'bellum_civile_caesar', 'bellum_africum', 'bellum_hispaniense',
    'annales_tacitus', 'historiae_tacitus', 'agricola', 'germania',
    'ab_urbe_condita', 'periochae',
    'naturalis_historia', 'panegyricus',
    'institutio_oratoria', 'controversiae', 'suasoriae',
    'confessiones', 'de_civitate_dei',
    'apology', 'symposium', 'phaedo', 'republic', 'laws', 'timaeus',
    'ethics', 'politics', 'rhetoric', 'metaphysics', 'poetics_aristotle',
    'histories_herodotus', 'peloponnesian', 'anabasis', 'hellenica', 'memorabilia',
    'lives', 'moralia', 'leucippe', 'varia_historia', 'fabulae', 'epitome',
    'against_ctesiphon', 'against_timarchus', 'on_the_embassy', 'orationes',
    'bible', 'vulgate', 'gospel', 'genesis', 'exodus', 'psalms', 'acts', 'romans',
    'metamorphoses', 'asinus_aureus', 'golden_ass', 'florida', 'apologia'
]

def detect_text_type(filename, content=None):
    """Detect if text is poetry or prose based on filename
    
    Default to poetry (line-based) since most classical texts in the corpus are poetic.
    Only mark as prose when confidently identified.
    Checks metadata overrides first.
    """
    override = get_override(filename)
    if 'text_type' in override:
        return override['text_type']
    
    name_lower = filename.lower().replace('.tess', '')
    
    for work in PROSE_WORKS:
        if work in name_lower:
            return 'prose'
    
    return 'poetry'

DISPLAY_NAMES = {
    'vergil': 'Vergil',
    'vergil_pseudo': 'Pseudo-Vergil',
    'cicero': 'Cicero',
    'ovid': 'Ovid',
    'horace': 'Horace',
    'lucan': 'Lucan',
    'statius': 'Statius',
    'juvenal': 'Juvenal',
    'martial': 'Martial',
    'catullus': 'Catullus',
    'propertius': 'Propertius',
    'tibullus': 'Tibullus',
    'lucretius': 'Lucretius',
    'seneca': 'Seneca',
    'seneca_younger': 'Seneca the Younger',
    'plautus': 'Plautus',
    'terence': 'Terence',
    'livy': 'Livy',
    'tacitus': 'Tacitus',
    'sallust': 'Sallust',
    'caesar': 'Caesar',
    'valerius_flaccus': 'Valerius Flaccus',
    'silius_italicus': 'Silius Italicus',
    'claudian': 'Claudian',
    'apuleius': 'Apuleius',
    'augustine': 'Augustine',
    'ammianus': 'Ammianus Marcellinus',
    'homer': 'Homer',
    'hesiod': 'Hesiod',
    'aeschylus': 'Aeschylus',
    'sophocles': 'Sophocles',
    'euripides': 'Euripides',
    'aristophanes': 'Aristophanes',
    'plato': 'Plato',
    'aristotle': 'Aristotle',
    'thucydides': 'Thucydides',
    'herodotus': 'Herodotus',
    'plutarch': 'Plutarch',
    'aeneid': 'Aeneid',
    'eclogues': 'Eclogues',
    'georgics': 'Georgics',
    'metamorphoses': 'Metamorphoses',
    'iliad': 'Iliad',
    'odyssey': 'Odyssey',
    'bellum_civile': 'Bellum Civile (Pharsalia)',
    'thebaid': 'Thebaid',
    'achilleid': 'Achilleid',
    'argonautica': 'Argonautica',
    'punica': 'Punica',
    'de_rerum_natura': 'De Rerum Natura',
    'ars_amatoria': 'Ars Amatoria',
    'amores': 'Amores',
    'fasti': 'Fasti',
    'tristia': 'Tristia',
    'heroides': 'Heroides',
    'odes': 'Odes',
    'carmina': 'Carmina',
    'satires': 'Satires',
    'epistles': 'Epistles',
    'ars_poetica': 'Ars Poetica',
    'rerum_gestarum': 'Res Gestae',
    'confessiones': 'Confessions',
    'de_civitate_dei': 'City of God',
    'cowper': 'Cowper',
    'task': 'The Task',
    'shakespeare': 'Shakespeare',
    'hamlet': 'Hamlet',
    'milton': 'Milton',
    'paradise_lost': 'Paradise Lost',
    'world_english_bible': 'World English Bible',
    'pentateuch': 'Pentateuch',
    'prophets': 'Prophets',
    'revelation': 'Revelation',
    'writings': 'Writings',
}

def format_display_name(raw_name):
    """Convert raw filename part to proper display name"""
    key = raw_name.lower().replace(' ', '_')
    if key in DISPLAY_NAMES:
        return DISPLAY_NAMES[key]
    return raw_name.replace('_', ' ').title()

def parse_part_number(part_str):
    """Parse part number and return display label"""
    part_str = part_str.lower()
    if part_str == 'fragments':
        return 'Fragments'
    try:
        num = int(part_str)
        return f'Book {num}'
    except ValueError:
        return part_str.title()

def get_text_metadata(filepath):
    """Extract metadata from a .tess filename with hierarchical structure"""
    filename = os.path.basename(filepath)
    name = filename.replace('.tess', '')
    
    parts = name.split('.')
    author_raw = parts[0] if len(parts) >= 1 else 'unknown'
    author = format_display_name(author_raw)
    
    work_raw = None
    work = None
    part_num = None
    part_display = None
    is_part = False
    
    if len(parts) >= 2:
        if 'part' in parts:
            part_idx = parts.index('part')
            work_raw = '.'.join(parts[1:part_idx])
            if part_idx + 1 < len(parts):
                part_num = parts[part_idx + 1]
                part_display = parse_part_number(part_num)
                is_part = True
        else:
            work_raw = '.'.join(parts[1:])
        
        work = format_display_name(work_raw) if work_raw else 'Unknown'
    else:
        work = format_display_name(name)
    
    if is_part and part_display:
        title = f"{work}, {part_display}"
    else:
        title = work
    
    text_type = detect_text_type(filename)
    
    override = get_override(filename)
    if 'display_author' in override:
        author = override['display_author']
    if 'display_work' in override:
        work = override['display_work']
        if is_part and part_display:
            title = f"{work}, {part_display}"
        else:
            title = work
    
    result = {
        'id': filename,
        'author': author,
        'author_key': author_raw,
        'work': work,
        'work_key': work_raw or name,
        'part': part_display,
        'part_num': part_num,
        'is_part': is_part,
        'title': title,
        'display_name': f"{author}, {title}",
        'filepath': filepath,
        'text_type': text_type
    }
    
    if 'year' in override:
        result['year'] = override['year']
    if 'era' in override:
        result['era'] = override['era']
    if override:
        result['has_override'] = True
    
    return result

def build_text_hierarchy(texts):
    """Build hierarchical structure: Author -> Work -> Parts"""
    hierarchy = {}
    
    for text in texts:
        author_key = text.get('author_key', text['author'].lower())
        work_key = text.get('work_key', text.get('work', '').lower())
        
        if author_key not in hierarchy:
            hierarchy[author_key] = {
                'author': text['author'],
                'works': {}
            }
        
        if work_key not in hierarchy[author_key]['works']:
            hierarchy[author_key]['works'][work_key] = {
                'work': text.get('work', text['title']),
                'whole_text': None,
                'parts': []
            }
        
        if text.get('is_part'):
            hierarchy[author_key]['works'][work_key]['parts'].append({
                'id': text['id'],
                'part': text.get('part'),
                'part_num': text.get('part_num'),
                'display': text.get('part', 'Part')
            })
        else:
            hierarchy[author_key]['works'][work_key]['whole_text'] = text['id']
    
    for author_key in hierarchy:
        for work_key in hierarchy[author_key]['works']:
            work = hierarchy[author_key]['works'][work_key]
            work['parts'].sort(key=lambda x: (
                int(x['part_num']) if x['part_num'] and x['part_num'].isdigit() else 999,
                x['part_num'] or ''
            ))
    
    return hierarchy

def load_text(filepath):
    """Load text content from a file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def save_results(results, filepath):
    """Save results to a file"""
    import json
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
