# Installing

## Claude chat (claude.ai) and Cowork — the one you asked for

Both read skills from the same place, so this is a single upload:

1. **Settings → Capabilities → Skills → Upload skill**
2. Upload `document-metadata-hygiene.zip`
3. Start a **new** conversation — skills are read at session start

It then applies in ordinary chat and in Cowork. Attach a document and say
*"check this for watermarks and metadata"*, or just *"clean this before I send
it"*. You do not need to name the skill.

### One caveat for chat and Cowork

The sandbox there may not have the Python libraries preinstalled. Claude will
run this automatically when needed, but if a run fails on an import:

```bash
pip install pypdf pymupdf
```

`pymupdf` is what makes the "is this text actually visible?" check possible, and
it is what stops the tool deleting a real heading. Don't skip it.

## Claude Code

```bash
mkdir -p ~/.claude/skills
cp -r document-metadata-hygiene ~/.claude/skills/
```

Per-project instead: copy to `<repo>/.claude/skills/` and commit it.

To rebuild the zip after editing:

```bash
zip -r document-metadata-hygiene.zip document-metadata-hygiene
```

### Skills, not memory

This belongs in **Skills**, not memory. Memory holds facts and standing
preferences that Claude reads as context. A skill is a procedure with executable
scripts attached. A memory entry saying "always strip metadata" would have no
script to run behind it.

## Optional: a hook for unconditional enforcement (Claude Code only)

A skill is *model-invoked*: Claude reads the description and decides whether it
applies. That is usually right, but it is a judgement call. For an actual
guarantee, use a `PostToolUse` hook — the harness runs it, no decision involved.

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/skills/document-metadata-hygiene/scripts/hook_scrub.sh"
          }
        ]
      }
    ]
  }
}
```

`hook_scrub.sh` scrubs **metadata only**. It never removes page content — that
always requires a human look at a rendered page first. It exits 0 silently when
no document was touched.

Verify:

```bash
echo '{"tool_input":{"file_path":"/tmp/probe.pdf"}}' \
  | ~/.claude/skills/document-metadata-hygiene/scripts/hook_scrub.sh
```

## What's in the box

| Script | Job |
| --- | --- |
| `audit_pdf.py` | 12 watermark/provenance vectors. Deliberately over-sensitive — expect false positives and read the table in `SKILL.md` before acting on any of them. |
| `find_hidden_text.py` | The narrow question: is any text genuinely invisible? Checks what is painted *behind* each span, so white-on-banner headings are not mistaken for watermarks. `--render` writes PNGs to look at. |
| `scrub_metadata.py` | Removes metadata from PDF / DOCX / XLSX / PPTX / PNG / JPEG. |
| `purge_orphans.py` | Removes Info dictionaries left orphaned in the file by pypdf's `clone_from`. **Run this after every PDF scrub** — without it the toolchain name survives in the raw bytes. |
| `hook_scrub.sh` | Claude Code hook wrapper, metadata only. |

## Check it works

```bash
cd ~/.claude/skills/document-metadata-hygiene
python3 scripts/scrub_metadata.py some-export.pdf --inspect
python3 scripts/find_hidden_text.py some-export.pdf
```

## Scope

This removes authoring and tooling metadata from files you own. It does not
remove C2PA / Content Credentials, ICC profiles, third-party copyright
watermarks, or classification and disclosure markings — see *Out of scope* in
`SKILL.md`.
