#!/bin/bash
#
# package_data.sh — Package Tesserae V6 index files for public download
#
# Run this on Marvin after building/updating index files.
# It compresses each .db file, generates SHA256 checksums,
# copies everything to the Apache public directory, and creates
# an HTML index page.
#
# Usage:
#   bash scripts/package_data.sh [--output-dir /path/to/public/dir]
#
# Default output: /var/www/tesseraev6_flask/public_data/
# The script will create the directory if it doesn't exist.

set -euo pipefail

TESSERAE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_OUTPUT_DIR="/var/www/tesseraev6_flask/public_data"
OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"

if [[ "${1:-}" == "--output-dir" ]] && [[ -n "${2:-}" ]]; then
    OUTPUT_DIR="$2"
elif [[ -n "${1:-}" ]] && [[ "${1:-}" != "--"* ]]; then
    OUTPUT_DIR="$1"
fi

DB_FILES=(
    "data/inverted_index/la_index.db"
    "data/inverted_index/grc_index.db"
    "data/inverted_index/en_index.db"
    "data/inverted_index/syntax_latin.db"
    "data/lemma_tables/latin_lemmas_extended.db"
)

DESCRIPTIONS=(
    "Latin inverted index (1,429 texts, 298,757 lemmas)"
    "Greek inverted index (659 texts, 360,429 lemmas)"
    "English inverted index (14 texts, 22,867 lemmas)"
    "Latin syntax parses — LatinPipe UD annotations (1,429 texts, 542,311 lines)"
    "Extended Latin lemma lookup table"
)

echo "=== Tesserae V6 Data Packager ==="
echo "Source: $TESSERAE_ROOT"
echo "Output: $OUTPUT_DIR"
echo ""

mkdir -p "$OUTPUT_DIR"

CHECKSUMS_FILE="$OUTPUT_DIR/SHA256SUMS.txt"
> "$CHECKSUMS_FILE"

for i in "${!DB_FILES[@]}"; do
    src="$TESSERAE_ROOT/${DB_FILES[$i]}"
    basename_db="$(basename "${DB_FILES[$i]}")"
    archive="${basename_db}.tar.gz"

    if [[ ! -f "$src" ]]; then
        echo "SKIP: $src not found"
        continue
    fi

    src_size=$(du -h "$src" | cut -f1)
    echo "Packaging: $basename_db ($src_size)..."

    tar -czf "$OUTPUT_DIR/$archive" -C "$(dirname "$src")" "$basename_db"

    archive_size=$(du -h "$OUTPUT_DIR/$archive" | cut -f1)
    echo "  -> $archive ($archive_size compressed)"

    cd "$OUTPUT_DIR"
    sha256sum "$archive" >> "$CHECKSUMS_FILE"
    cd "$TESSERAE_ROOT"
done

echo ""
echo "Checksums written to $CHECKSUMS_FILE:"
cat "$CHECKSUMS_FILE"

echo ""
echo "Updating DATA_MANIFEST.json with checksums..."

MANIFEST="$TESSERAE_ROOT/DATA_MANIFEST.json"
if [[ -f "$MANIFEST" ]] && command -v python3 &>/dev/null; then
    python3 -c "
import json, re

with open('$CHECKSUMS_FILE') as f:
    checksums = {}
    for line in f:
        parts = line.strip().split()
        if len(parts) == 2:
            checksums[parts[1]] = parts[0]

with open('$MANIFEST') as f:
    manifest = json.load(f)

updated = 0
for entry in manifest['files']:
    fname = entry['filename']
    if fname in checksums:
        entry['sha256'] = checksums[fname]
        updated += 1

with open('$MANIFEST', 'w') as f:
    json.dump(manifest, f, indent=2)
    f.write('\n')

print(f'  Updated {updated} checksums in DATA_MANIFEST.json')
"
else
    echo "  (Manual update needed — copy checksums from $CHECKSUMS_FILE into DATA_MANIFEST.json)"
fi

BUILD_DATE=$(date -u '+%Y-%m-%d')
cat > "$OUTPUT_DIR/index.html" << HTMLEOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tesserae V6 — Data Files</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }
        h1 { color: #1a365d; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }
        h2 { color: #2d3748; margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #e2e8f0; }
        th { background: #f7fafc; font-weight: 600; }
        a { color: #2b6cb0; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .note { background: #f0fff4; border-left: 4px solid #48bb78; padding: 12px 16px; margin: 20px 0; border-radius: 4px; }
        code { background: #edf2f7; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
        pre { background: #2d3748; color: #e2e8f0; padding: 16px; border-radius: 6px; overflow-x: auto; }
    </style>
</head>
<body>
    <h1>Tesserae V6 — Data Files</h1>
    <p>Pre-built search indexes for <a href="https://github.com/tesserae/tesserae-v6">Tesserae V6</a>. These files are required to run the application but are too large for GitHub.</p>

    <div class="note">
        <strong>Quick setup:</strong> Clone the repo, then run <code>python scripts/download_data.py</code> to download all files automatically.
    </div>

    <h2>Available Files</h2>
    <table>
        <tr><th>File</th><th>Size</th><th>Description</th></tr>
HTMLEOF

for i in "${!DB_FILES[@]}"; do
    basename_db="$(basename "${DB_FILES[$i]}")"
    archive="${basename_db}.tar.gz"
    if [[ -f "$OUTPUT_DIR/$archive" ]]; then
        archive_size=$(du -h "$OUTPUT_DIR/$archive" | cut -f1)
        db_size=$(du -h "$TESSERAE_ROOT/${DB_FILES[$i]}" 2>/dev/null | cut -f1 || echo "?")
        cat >> "$OUTPUT_DIR/index.html" << ROWEOF
        <tr>
            <td><a href="$archive">$archive</a></td>
            <td>${archive_size} (${db_size} uncompressed)</td>
            <td>${DESCRIPTIONS[$i]}</td>
        </tr>
ROWEOF
    fi
done

cat >> "$OUTPUT_DIR/index.html" << HTMLEOF
        <tr>
            <td><a href="SHA256SUMS.txt">SHA256SUMS.txt</a></td>
            <td>—</td>
            <td>Checksums for verifying downloads</td>
        </tr>
    </table>

    <h2>Setup Instructions</h2>
    <pre>
# 1. Clone the repository
git clone https://github.com/tesserae/tesserae-v6.git
cd tesserae-v6

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Download data files (~5.3 GB)
python scripts/download_data.py

# 4. Start the application
python main.py</pre>

    <h2>What's Included in Git vs. Here</h2>
    <table>
        <tr><th>Data</th><th>Location</th></tr>
        <tr><td>Text corpus (2,176 .tess files)</td><td>Git repository</td></tr>
        <tr><td>Semantic embeddings (~2 GB)</td><td>Git repository</td></tr>
        <tr><td>Lemma tables (JSON, ~40 MB)</td><td>Git repository</td></tr>
        <tr><td>Metrical scansion data</td><td>Git repository</td></tr>
        <tr><td><strong>Search indexes (~3.7 GB)</strong></td><td><strong>This page</strong></td></tr>
        <tr><td><strong>Syntax parse DB (~1.6 GB)</strong></td><td><strong>This page</strong></td></tr>
    </table>

    <p><em>Last updated: ${BUILD_DATE}</em></p>
</body>
</html>
HTMLEOF

echo ""
echo "HTML index page created at $OUTPUT_DIR/index.html"
echo ""
echo "=== Done ==="
echo ""
echo "Files in $OUTPUT_DIR:"
ls -lh "$OUTPUT_DIR"
echo ""
echo "Next steps:"
echo "  1. Ensure Apache serves $OUTPUT_DIR (check your Apache config)"
echo "  2. Commit the updated DATA_MANIFEST.json to Git"
echo "  3. Test: curl -I https://tesserae.caset.buffalo.edu/tesserae-data/la_index.db.tar.gz"
