#!/usr/bin/env bash
# PostToolUse hook: scrub authoring metadata from any document a tool call wrote.
#
# Reads the tool payload as JSON on stdin, extracts candidate file paths, and
# scrubs in place any that exist and are a supported document type. Silent and
# exit 0 when nothing matches, so unrelated tool calls are unaffected.
#
# Wire up in ~/.claude/settings.json under hooks.PostToolUse — see INSTALL.md.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRUB="$HERE/scrub_metadata.py"
PY="${PYTHON:-python3}"

[ -f "$SCRUB" ] || exit 0
command -v "$PY" >/dev/null 2>&1 || exit 0

payload="$(cat 2>/dev/null || true)"
[ -n "$payload" ] || exit 0

# Pull plausible paths out of the payload: explicit file_path fields plus any
# document-looking token in the command string. Python does the parsing so we
# are not at the mercy of shell quoting.
mapfile -t files < <(
  PAYLOAD="$payload" "$PY" - <<'EOF' 2>/dev/null
import json, os, re, shlex, sys

raw = os.environ.get("PAYLOAD", "")
EXT = (".pdf", ".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm",
       ".png", ".jpg", ".jpeg")

try:
    data = json.loads(raw)
except Exception:
    data = {}

cands = []

def walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("file_path", "filePath", "path", "notebook_path") and isinstance(v, str):
                cands.append(v)
            elif k in ("command", "content", "new_string") and isinstance(v, str):
                try:
                    cands.extend(shlex.split(v))
                except ValueError:
                    cands.extend(v.split())
            else:
                walk(v)
    elif isinstance(node, list):
        for v in node:
            walk(v)

walk(data)
if not cands:
    cands = re.findall(r"[\w./~-]+(?:" + "|".join(re.escape(e) for e in EXT) + ")", raw)

seen, out = set(), []
for c in cands:
    c = c.strip().strip("'\"")
    if not c.lower().endswith(EXT):
        continue
    p = os.path.abspath(os.path.expanduser(c))
    if p in seen or not os.path.isfile(p):
        continue
    seen.add(p)
    out.append(p)

print("\n".join(out))
EOF
)

[ "${#files[@]}" -gt 0 ] || exit 0

for f in "${files[@]}"; do
  [ -n "$f" ] || continue
  before="$("$PY" "$SCRUB" "$f" --inspect 2>/dev/null | grep -c 'would remove' || true)"
  if [ "${before:-0}" -gt 0 ]; then
    if "$PY" "$SCRUB" "$f" --in-place >/dev/null 2>&1; then
      echo "metadata-hygiene: scrubbed $before field(s) from $(basename "$f")"
    fi
  fi
done

exit 0
