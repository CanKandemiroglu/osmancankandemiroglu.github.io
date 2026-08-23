# Vendored typefaces

Self-hosted so the CV page (`/cv.html`) can use the typography of its design
source without issuing a third-party request. Nothing here is fetched from a
CDN at page load — the site's Datenschutzerklärung lists every external call,
and these fonts deliberately do not add one.

| File | Family | Subset | Source |
| --- | --- | --- | --- |
| `caprasimo-latin.woff2`, `caprasimo-latin-ext.woff2` | Caprasimo (400) | latin, latin-ext | Google Fonts, `caprasimo` v6 |
| `figtree-latin.woff2`, `figtree-latin-ext.woff2` | Figtree (variable, 300–900) | latin, latin-ext | Google Fonts, `figtree` v9 |

The `@font-face` declarations, including the `unicode-range` subsetting these
files were cut for, live in `assets/css/cv.css`.

Both families are licensed under the SIL Open Font License, Version 1.1:

- Caprasimo — Copyright 2023 The Caprasimo Project Authors
  (https://github.com/docrepair-fonts/caprasimo-fonts) — see `OFL-Caprasimo.txt`
- Figtree — Copyright 2022 The Figtree Project Authors
  (https://github.com/erikdkennedy/figtree) — see `OFL-Figtree.txt`
