---
name: document-metadata-hygiene
description: Audit and remove authoring metadata and hidden watermarks from documents before they are sent to anyone — producer/creator strings that name the software or machine (e.g. "HeadlessChrome", "Skia/PDF", "XeTeX", "Microsoft Office Word"), author and company fields, revision counts, creation timestamps, orphaned metadata objects, and genuinely invisible text. Use whenever exporting, generating, converting or delivering a PDF, DOCX, XLSX, PPTX, PNG or JPEG the user owns — especially job applications, CVs, cover letters, manuscripts and anything submitted to an external party. Do not use to remove C2PA/Content Credentials, provenance marks, third-party copyright watermarks, or required disclosures and classification markings.
---

# Document metadata hygiene

Files carry more than their content. A PDF rendered by headless Chrome announces
`HeadlessChrome/141.0.0.0` and `Skia/PDF` in its Creator and Producer fields; a
LaTeX build announces `XeTeX` and the minute it finished; a DOCX carries the
author name, the last editor's machine login and a revision count. None of it is
visible when the document is read, and all of it ships to whoever receives the
file.

Removing it is ordinary hygiene for documents the user owns.

## The rule that matters most

**Do not remove anything you have not rendered and looked at.**

Watermark-shaped signals in a content stream are not evidence of a watermark.
The single most important distinction:

> **White text is only invisible if nothing is painted behind it.**
> White on a dark banner is a heading. White on a white page is a watermark.
> They are identical in the content stream.

This is not hypothetical. In a real motivation letter, a heading reading
`THE CLAIM UNDER TEST` lit up every classic signal — white fill, alpha 0.85,
inside an isolated transparency group, drawn via a Form XObject. It was removed
as a hidden watermark. It was a **visible section heading on a red banner**, and
the delivered PDF had a blank orange gap where the heading belonged. The error
survived a byte-level "verification" that only checked the watermark was gone,
never that the page still looked right.

So the order of operations is fixed:

1. Audit — `audit_pdf.py` (broad, deliberately over-sensitive)
2. Narrow — `find_hidden_text.py` (asks what is painted behind)
3. **Render and look** — `--render`, then actually view the PNG
4. Only then remove, and only the specific thing you confirmed
5. Render again and compare against the original, span for span

Steps 3 and 5 are not optional. A watermark left in place is a small problem; a
heading silently deleted from a job application is a much larger one.

## Run it

```bash
S=scripts

python3 $S/audit_pdf.py         file.pdf            # 12 vectors, over-sensitive
python3 $S/find_hidden_text.py  file.pdf            # what is genuinely invisible
python3 $S/find_hidden_text.py  file.pdf --render r/  # PNGs to eyeball
python3 $S/scrub_metadata.py    file.pdf --inspect  # report only, writes nothing
python3 $S/scrub_metadata.py    file.pdf -o out/    # cleaned copy
python3 $S/purge_orphans.py     out/file.pdf        # MUST run after scrubbing
```

Always `--inspect` first on a file the user supplied, so they can see what is
about to go. Report what was actually removed, quoting values: "removed Creator
= HeadlessChrome/141.0.0.0", not "stripped metadata".

## Always run purge_orphans.py after scrubbing

`PdfWriter(clone_from=...)` copies **every** object in the source, including the
original Info dictionary. `add_metadata({})` then creates a *new* empty Info
object and repoints the trailer — but the original is still in the file, byte
for byte, merely unreferenced. `pypdf` reports the metadata as empty. `strings
file.pdf` shows `HeadlessChrome` anyway.

Verification must therefore be done on **raw bytes**, not through the library
that wrote the file:

```bash
strings file.pdf | grep -Ei 'headless|skia|xetex|dvipdfmx|microsoft|producer'
```

## False positives — investigate, don't strip

`audit_pdf.py` is intentionally noisy. Almost everything it flags on a normal
document is benign. Known patterns:

| Flag | Usually means | Tell |
| --- | --- | --- |
| "rotated text" | synthetic italic | matrix `(1, 0, 0.25, -1)` — `b=0` means no rotation; `c` is shear |
| "annotation" | a mailto/URL link | `/Subtype /Link`, not `/Watermark` |
| "white text" | a badge or banner heading | a filled dark rect covers its bbox |
| "transparency" | ordinary design | alpha 0.85 on a *visible* element |
| "invisible Unicode" (PUA) | broken ToUnicode CMap | the glyphs render as normal punctuation |
| "fonts embedded 0/N" | Type 3 fonts | glyphs are inline procedures; there is no font file to embed |

A genuine visual watermark normally shows several of: faded alpha **and** no
backdrop, rotation with a real non-zero `b`, an OCG layer, or an image XObject
stamped across the page. One signal alone is not enough.

## Removing content, when it is genuinely warranted

Two pypdf traps, both of which silently produce a file that looks correct:

**`page.get_contents()` returns a disconnected copy.** Mutating it changes
nothing that gets written. Prove identity before trusting an edit:

```python
from pypdf import PdfWriter
from pypdf.generic import NameObject

writer = PdfWriter(clone_from=src)          # not PdfReader + add_page
page   = writer.pages[0]
direct = page.raw_get("/Contents").get_object()   # not page.get_contents()
assert direct is page.raw_get("/Contents").get_object()

data = direct.get_data()
new, n = pattern.subn(b"", data)
direct.set_data(new)

res = page["/Resources"]
del res["/XObject"].get_object()[NameObject("/X17")]
del res["/ExtGState"].get_object()[NameObject("/G16")]
```

**Deleting a resource after `add_page()` orphans it** — the object is still
cloned into the output, just unreferenced, and still recoverable. Mutate within
the writer.

**A raw byte grep cannot verify removal.** Content streams are Flate-compressed,
so grepping the file for `/X17` returns 0 whether or not the invocation is still
there. Decompress every stream first, then search.

## What it removes

| Format | Removed |
| --- | --- |
| PDF | Info dict (Title, Author, Subject, Keywords, Creator, Producer, CreationDate, ModDate), XMP packet, orphaned Info objects |
| DOCX / XLSX / PPTX | `dc:creator`, `cp:lastModifiedBy`, `cp:revision`, timestamps, `Application`, `AppVersion`, `Company`, `TotalTime`; drops `docProps/custom.xml`; normalises zip entry timestamps |
| PNG | `tEXt`, `iTXt`, `zTXt`, `tIME`, `eXIf` chunks |
| JPEG | APP1 (EXIF/XMP), APP13 (IPTC/Photoshop), COM comments |

## What it deliberately keeps

- **C2PA / Content Credentials** — JPEG APP11 (JUMBF) and PDF attachments. These
  record where a file came from. Stripping them is not metadata hygiene.
- **ICC colour profiles** — JPEG APP2, PNG `iCCP`/`sRGB`/`gAMA`/`cHRM`.
- **JFIF APP0** and every critical PNG chunk — required to render.
- **All page content, fonts and structure.**

## Out of scope

Do not use this skill, or write new code, to do any of the following. If asked,
say plainly that it is outside what this covers and stop:

- Removing **AI provenance marks** — C2PA, SynthID-class signals, or model
  watermarks — so that generated content stops being identifiable as generated.
- Removing a **third party's copyright watermark, credit line or attribution**
  from an image or document the user does not own.
- Removing **"DRAFT", "CONFIDENTIAL", classification banners or required
  disclosures**. These are there on purpose; ask before touching them.
- **Rewriting prose to defeat AI-text detection.** Metadata hygiene changes what
  the file records about its own creation. It does not change how the writing
  reads, and it must never be described to the user as if it did.

If a request looks like one of these, the honest answer is that metadata removal
does not accomplish it — say so rather than doing something adjacent and letting
the user assume it worked.

## Invisible Unicode

Documents assembled from mixed sources can pick up zero-width spaces, word
joiners, bidi controls and soft hyphens.

```bash
python3 - "$FILE" <<'EOF'
import sys, unicodedata
t = open(sys.argv[1], encoding='utf-8', errors='replace').read()
bad = [(i, c) for i, c in enumerate(t) if unicodedata.category(c) in ('Cf','Co','Cs')]
print(f"{len(bad)} invisible/format characters")
for i, c in bad[:40]:
    print(f"  @{i} U+{ord(c):04X} {unicodedata.name(c,'?')}")
EOF
```

Remove only what is genuinely stray. Leave load-bearing characters alone: ZWJ in
emoji sequences, ZWNJ in Persian/Arabic/Indic orthography, RTL marks in
bidirectional text, and variation selectors. A `µ`, `δ`, `á`, en dash or `→` in
scientific prose is content, not contamination — never "clean" those away.

## Verifying — the checklist that would have caught the mistake

```python
import pymupdf
a, b = pymupdf.open(original), pymupdf.open(cleaned)
assert a.page_count == b.page_count
assert "".join(p.get_text() for p in a) == "".join(p.get_text() for p in b)
for pa, pb in zip(a, b):
    sa = [("".join(chr(c[0]) for c in s["chars"]), s["color"]) for s in pa.get_texttrace()]
    sb = [("".join(chr(c[0]) for c in s["chars"]), s["color"]) for s in pb.get_texttrace()]
    assert sa == sb, "a visible span changed"   # unless you meant to remove it
```

`get_text()` does **not** reach text inside Form XObjects — it can report
"identical" while a heading has vanished. `get_texttrace()` does see it. Use
both, plus a rendered PNG of every page you changed.

Also confirm: page dimensions unchanged, fonts still embedded (`/FontFile`,
`/FontFile2`, `/FontFile3`), and `strings` finds no toolchain names.
