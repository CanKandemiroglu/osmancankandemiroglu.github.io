# References — Ph.D. position HypoWaves (Bio 01/2026)

The referee sheet for Osman Can Kandemiroglu's application to the HypoWaves
Ph.D. position, reference **Bio 01/2026**.

Implemented from the Claude Design project
[`Reference Sheet.dc.html`](https://claude.ai/design/p/cf1a46b7-26ca-4443-a813-f4071d5f7bd0),
which draws on the *Organic* design system (`_ds/organic-4e40b301…`).
Content is a one-to-one transcription of `uploads/IOW_Bio01-2026_REFERENCE_SHEET.md`
in that project — no facts were added, dropped, or reworded.

## Files

| File | What it is |
| --- | --- |
| `references.html` | The document. Static HTML — open it in any browser. |
| `assets/organic.css` | *Organic* design tokens, as published by the design system. |
| `assets/sheet.css` | Paged-document shell: A4/Letter page box, margins, repeating footer. |
| `assets/fonts.css` | Caprasimo + Figtree (SIL OFL), embedded as `data:` URIs. |
| `export-pdf.sh` | Renders the document to PDF with headless Chromium. |
| `scrub-metadata.py` | Strips the renderer's fingerprint from the PDF's Info dictionary. |

## What the design's runtime became

The source is a `.dc.html` canvas document: it renders through Claude Design's
runtime (`support.js` pulls React and Babel from unpkg to evaluate the `<x-dc>`
template) inside a `<doc-page>` web component, and its `<script data-dc-script>`
block declares two editor props.

None of that survives here, and none of it needs to. The document is static —
no React, no Babel, no custom elements, no network at render time:

- **`<doc-page size="a4" margin="0.8in">`** → `assets/sheet.css`. The flowing-mode
  behaviour that matters for print is reproduced directly: `@page { size: A4;
  margin: 0 }` so Chrome draws no date/URL furniture of its own, the visual
  margin on the sheet's padding, and the running footer carried by a
  single-cell table whose `<thead>`/`<tfoot>` spacers browsers repeat on every
  printed page.
- **`<sc-if value="{{ fullDetail }}">`** → a `data-detail` attribute on `<html>`.
- **The `paperSize` and `detail` props** → URL parameters, below.
- **`_ds_bundle.js`** → nothing. The bundle declares no components; *Organic* is
  pure CSS.

## Variants

| URL | Output |
| --- | --- |
| `references.html` | A4, full detail — the default. |
| `references.html?paper=letter` | US Letter. |
| `references.html?detail=contacts` | "Contacts only": names, roles and office contacts, without the relationship and letter notes. |

## Exporting the PDF

```sh
./export-pdf.sh                                # Kandemiroglu_References_Bio-01-2026.pdf, A4
./export-pdf.sh letter.pdf 'paper=letter'      # US Letter
./export-pdf.sh short.pdf  'detail=contacts'   # contacts-only
```

Needs headless Chromium (set `CHROME=/path/to/chrome` if it is not on `PATH`)
and python3 — nothing else. Fonts are embedded, so the render is offline and
reproducible. Output is one A4 page with selectable text.

`export-pdf.sh` finishes by running `scrub-metadata.py`, which rewrites the
PDF's Info dictionary: the `HeadlessChrome/141…` user-agent Chromium writes into
`/Creator` and the `Skia/PDF` producer string are replaced with authored values.
Nothing ships announcing how it was rendered.

PDFs are gitignored — they are build output, and belong in the application
folder next to the letter and CV rather than in a repository GitHub Pages serves.

## A note on publishing

This page carries two referees' office contact details and Osman's own mobile
number. It is marked `noindex, nofollow` and is linked from nowhere on the
site — but GitHub Pages serves every file in this repository, so anyone with
the URL can read it. If that is not wanted, the directory should move out of
the published repository entirely.
