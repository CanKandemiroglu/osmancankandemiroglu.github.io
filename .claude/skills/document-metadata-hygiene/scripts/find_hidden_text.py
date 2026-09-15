#!/usr/bin/env python3
"""Find text a reader cannot see -- and, crucially, don't cry wolf.

audit_pdf.py answers "does this file use any watermark-shaped feature?".  That
question has many false-positive answers: synthetic italic looks like rotation,
a mailto link looks like an annotation, white text looks invisible.  This script
answers the narrower and far more useful question:

    is there text here that a human reading the page would not see?

The rule that matters, learned the hard way:

    WHITE TEXT IS ONLY INVISIBLE IF NOTHING IS PAINTED BEHIND IT.

White text on a dark banner is a section heading.  White text on a white page is
a watermark.  They look identical in the content stream.  The only way to tell
them apart is to ask what was drawn underneath, which is what this script does:
for every suspicious span it searches the page's vector drawings for a filled
shape covering that span's bounding box, and compares the two colours.

Skipping that check has a concrete cost.  In one real document a heading reading
"THE CLAIM UNDER TEST" -- white, alpha 0.85, inside an isolated transparency
group, every classic watermark signal lit up -- turned out to be a visible
heading on a red banner.  It was deleted, and the delivered PDF had a blank gap
where the heading belonged.  Content-stream signals alone were not enough, and
they never are.

Requires PyMuPDF, which is a real renderer:  pip install pymupdf

Usage:
    python3 find_hidden_text.py file.pdf [more.pdf ...]
    python3 find_hidden_text.py file.pdf --all      # list every text span
    python3 find_hidden_text.py file.pdf --render out/   # PNG per page to eyeball
"""

import os
import sys

try:
    import pymupdf
except ImportError:  # pragma: no cover
    try:
        import fitz as pymupdf
    except ImportError:
        sys.exit("PyMuPDF required:  pip install pymupdf")

NEAR_WHITE = 0.95
# Text render mode 3 = invisible, 7 = add-to-clip-path only.  Both paint nothing.
INVISIBLE_TYPES = {3, 7}


def luma(c):
    if c is None:
        return None
    if isinstance(c, (int, float)):
        return float(c)
    if len(c) == 1:
        return float(c[0])
    if len(c) >= 3:
        r, g, b = c[0], c[1], c[2]
        return 0.299 * r + 0.587 * g + 0.114 * b
    return None


def backdrop(page, bbox, drawings):
    """The colour painted behind bbox, or None if only the bare page is there.

    Returns (luma, fill_tuple, rect) of the topmost filled shape that covers the
    span.  Later drawings paint over earlier ones, so we take the last match.
    """
    hit = None
    r = pymupdf.Rect(bbox)
    for d in drawings:
        fill = d.get("fill")
        if fill is None:
            continue
        dr = d.get("rect")
        if dr is None:
            continue
        # Ignore a full-page white background: that is the paper, not a backdrop.
        if dr.width >= page.rect.width * 0.98 and dr.height >= page.rect.height * 0.98:
            if luma(fill) is not None and luma(fill) >= NEAR_WHITE:
                continue
        if dr.contains(r) or (dr & r).get_area() >= r.get_area() * 0.6:
            hit = (luma(fill), tuple(round(float(x), 3) for x in fill), dr)
    return hit


def classify(span, page, drawings):
    """Return (verdict, reason).  SUSPECT = a reader would not see this."""
    typ = span.get("type", 0)
    op = float(span.get("opacity", 1.0) or 1.0)
    col = span.get("color")
    lu = luma(col)

    if typ in INVISIBLE_TYPES:
        return "SUSPECT", f"text render type {typ} paints nothing"
    if op <= 0.05:
        return "SUSPECT", f"opacity {op}"

    if lu is not None and lu >= NEAR_WHITE:
        back = backdrop(page, span["bbox"], drawings)
        if back is None:
            return "SUSPECT", (
                f"white text (luma {lu:.2f}) with nothing painted behind it "
                f"-- invisible on the page"
            )
        blu, bfill, brect = back
        if blu is not None and blu >= NEAR_WHITE:
            return "SUSPECT", (
                f"white text on a white-ish fill {bfill} -- no contrast"
            )
        return "ok", (
            f"white text on dark fill {bfill} (luma {blu:.2f}) -- visible, a "
            f"heading or badge; LEAVE IT ALONE"
        )

    if op < 0.6:
        back = backdrop(page, span["bbox"], drawings)
        where = "over a fill" if back else "on bare page"
        return "REVIEW", f"opacity {op} {where} -- faded, check by eye"

    return "ok", ""


def report(path, show_all=False, render_dir=None):
    print(f"\n=== {path} ===")
    try:
        doc = pymupdf.open(path)
    except Exception as e:
        print(f"  cannot open: {e}")
        return 0

    suspect = 0
    for pno, page in enumerate(doc, 1):
        try:
            spans = page.get_texttrace()
            drawings = page.get_drawings()
        except Exception as e:
            print(f"  page {pno}: {e}")
            continue

        rows = []
        for s in spans:
            verdict, reason = classify(s, page, drawings)
            if verdict != "ok" or show_all:
                rows.append((verdict, reason, s))

        shown = [r for r in rows if r[0] != "ok"]
        print(f"  page {pno}: {len(spans)} spans, {len(shown)} flagged")
        for verdict, reason, s in rows:
            txt = "".join(chr(c[0]) for c in s["chars"])[:75]
            if verdict == "SUSPECT":
                suspect += 1
            bb = tuple(round(v) for v in s["bbox"])
            print(f"    [{verdict}] {bb} {txt!r}")
            if reason:
                print(f"            {reason}")

        if render_dir:
            os.makedirs(render_dir, exist_ok=True)
            out = os.path.join(
                render_dir, f"{os.path.basename(path)}.p{pno}.png"
            )
            page.get_pixmap(dpi=110).save(out)
            print(f"    rendered -> {out}")

    if suspect:
        print(f"\n  --> {suspect} span(s) a reader would not see.")
        print("      Before removing ANY of them: render the page and look at it.")
        print("      Removing a visible heading is worse than leaving a watermark.")
    else:
        print("\n  No invisible text. Anything flagged REVIEW is visible but faint.")
    return suspect


def main():
    argv = sys.argv[1:]
    files = [a for a in argv if not a.startswith("-")]
    show_all = "--all" in argv
    render_dir = None
    if "--render" in argv:
        i = argv.index("--render")
        render_dir = argv[i + 1] if i + 1 < len(argv) else "render_out"
        files = [f for f in files if f != render_dir]
    if not files:
        sys.exit(__doc__)
    worst = 0
    for f in files:
        worst = max(worst, report(f, show_all, render_dir))
    return 1 if worst else 0


if __name__ == "__main__":
    sys.exit(main())
