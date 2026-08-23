#!/usr/bin/env bash
# Render references.html to PDF with headless Chromium.
#
# The document owns its own print geometry (@page size + margin: 0 in
# assets/sheet.css), so --no-pdf-header-footer is all that is needed to keep
# the browser from stamping its own date/URL furniture on top. Fonts are
# embedded as data: URIs in assets/fonts.css — the render needs no network.
#
# The rendered file is then passed through scrub-metadata.py, which strips
# the HeadlessChrome user-agent and the Skia producer string out of the PDF's
# Info dictionary — nothing ships announcing how it was rendered.
#
# Usage: ./export-pdf.sh [output.pdf] [query-string]
#   ./export-pdf.sh                                  # A4, full detail
#   ./export-pdf.sh letter.pdf 'paper=letter'        # US Letter
#   ./export-pdf.sh short.pdf  'detail=contacts'     # contacts-only variant
set -euo pipefail

cd "$(dirname "$0")"
out="${1:-Kandemiroglu_References_Bio-01-2026.pdf}"
query="${2:-}"
src="file://$PWD/references.html${query:+?$query}"

chrome="${CHROME:-}"
if [ -z "$chrome" ]; then
  for c in /opt/pw-browsers/chromium chromium chromium-browser google-chrome; do
    if command -v "$c" >/dev/null 2>&1 || [ -x "$c" ]; then chrome="$c"; break; fi
  done
fi
[ -n "$chrome" ] || { echo "No Chromium found. Set CHROME=/path/to/chrome" >&2; exit 1; }

"$chrome" --headless=new --disable-gpu --no-sandbox \
  --virtual-time-budget=10000 \
  --no-pdf-header-footer \
  --print-to-pdf="$out" \
  "$src" 2>/dev/null

# Pre-flight: strip the renderer's fingerprint before the file goes anywhere.
python3 "$(dirname "$0")/scrub-metadata.py" "$out" \
  --author "Osman Can Kandemiroglu" \
  --subject "References - Ph.D. position HypoWaves, reference Bio 01/2026" \
  --creator "Osman Can Kandemiroglu"

echo "wrote $out"
