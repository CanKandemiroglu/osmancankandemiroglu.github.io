# /cv

Osman Can Kandemiroglu's curriculum vitae, authored as a Claude Design
document and exported to a two-page PDF.

| Path | What it is |
| --- | --- |
| `design/` | Verbatim mirror of the Claude Design project (`Kandemiroglu Resume Modernist.dc.html` plus its `_ds/` design-system tokens, `doc-page.js` and `support.js` runtime files) — the editable source of truth. |
| `resume.html` | Static, standalone print target derived from `design/Kandemiroglu Resume Modernist.dc.html`: the same two `<section class="page">` bodies and `<style>` block, wired directly to `design/doc-page.js` and the design-system stylesheet instead of the full React-based DC editor runtime. The design's three toggles (`showTargetLine`, `pageNumbers`, `refereeContact`) are all `true` by default, so this resolves those `<sc-if>` blocks statically. |
| `Kandemiroglu_CV.pdf` | The rendered two-page A4 PDF, generated from `resume.html`. |

## Regenerating the PDF

`doc-page.js` (vendored from the design project) owns the `@page` geometry —
one A4 sheet per `.page` section — so any headless-Chromium print-to-PDF
reproduces the design exactly:

```sh
node -e "
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + path.resolve('cv/resume.html'), { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({ path: 'cv/Kandemiroglu_CV.pdf', printBackground: true, preferCSSPageSize: true });
  await browser.close();
})();
"
```

If the CV content changes in Claude Design, re-sync `design/Kandemiroglu
Resume Modernist.dc.html`, re-apply the same static resolution to
`resume.html` (unwrap the `<sc-if>` blocks for the toggle values you want
baked into the PDF), and re-run the export above.
