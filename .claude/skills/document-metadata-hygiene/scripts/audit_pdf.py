#!/usr/bin/env python3
"""Audit PDFs for watermarks, provenance marks and metadata leakage."""
import re, sys, zlib, unicodedata
from pathlib import Path
from pypdf import PdfReader

VECTORS = [
    "Info dict metadata", "XMP packet", "Watermark annotations",
    "Optional content (OCG layers)", "Transparency / alpha", "Rotated text",
    "Image XObjects", "Invisible text (Tr 3)", "Embedded files / attachments",
    "C2PA / Content Credentials", "JavaScript / OpenAction", "Invisible Unicode",
]


def streams(raw: bytes):
    for m in re.finditer(rb"stream\r?\n", raw):
        s = m.end()
        e = raw.find(b"endstream", s)
        try:
            yield zlib.decompress(raw[s:e])
        except Exception:
            yield raw[s:e]


def audit(path: Path) -> dict:
    raw = path.read_bytes()
    r = PdfReader(str(path))
    f = {}

    meta = {k: v for k, v in (r.metadata or {}).items() if v}
    f["Info dict metadata"] = [f"{k} = {str(v)[:95]}" for k, v in meta.items()]

    f["XMP packet"] = ["/Metadata stream present"] if b"<x:xmpmeta" in raw else []

    annots, wm = 0, 0
    for pg in r.pages:
        for a in (pg.get("/Annots") or []):
            annots += 1
            try:
                if str(a.get_object().get("/Subtype")) == "/Watermark":
                    wm += 1
            except Exception:
                pass
    f["Watermark annotations"] = (
        [f"{annots} annotation(s), {wm} of subtype /Watermark"] if annots else []
    )

    ocg = raw.count(b"/OCProperties") + raw.count(b"/OCG")
    f["Optional content (OCG layers)"] = [f"{ocg} OCG marker(s)"] if ocg else []

    alphas = {
        (m.group(1).decode(), m.group(2).decode())
        for m in re.finditer(rb"/(CA|ca)\s+([0-9.]+)", raw)
    }
    faded = [f"/{k} {v}" for k, v in sorted(alphas) if float(v) < 1.0]
    f["Transparency / alpha"] = faded

    rot = 0
    for t in streams(raw):
        for m in re.finditer(rb"([-0-9.]+) ([-0-9.]+) ([-0-9.]+) ([-0-9.]+) "
                             rb"[-0-9.]+ [-0-9.]+ Tm", t):
            b_, c_ = float(m.group(2)), float(m.group(3))
            if abs(b_) > 1e-6 or abs(c_) > 1e-6:
                rot += 1
    f["Rotated text"] = [f"{rot} rotated text matrix/matrices"] if rot else []

    imgs = []
    for pg in r.pages:
        xo = (pg.get("/Resources") or {}).get("/XObject")
        if not xo:
            continue
        for name, ref in xo.get_object().items():
            try:
                o = ref.get_object()
                if str(o.get("/Subtype")) == "/Image":
                    imgs.append(f"{name} {o.get('/Width')}x{o.get('/Height')}")
            except Exception:
                pass
    f["Image XObjects"] = imgs

    inv = sum(len(re.findall(rb"\b3\s+Tr\b", t)) for t in streams(raw))
    f["Invisible text (Tr 3)"] = [f"{inv} invisible-render-mode operator(s)"] if inv else []

    emb = raw.count(b"/EmbeddedFile") + raw.count(b"/Filespec")
    f["Embedded files / attachments"] = [f"{emb} marker(s)"] if emb else []

    c2pa = [k for k in (b"c2pa", b"jumbf", b"contentauth", b"C2PA") if k in raw]
    f["C2PA / Content Credentials"] = [f"marker {k.decode()!r}" for k in c2pa]

    js = raw.count(b"/JavaScript") + raw.count(b"/JS") + raw.count(b"/OpenAction")
    f["JavaScript / OpenAction"] = [f"{js} marker(s)"] if js else []

    text = "\n".join((p.extract_text() or "") for p in r.pages)
    bad = [c for c in text if unicodedata.category(c) in ("Cf", "Co", "Cs")]
    seen = sorted({f"U+{ord(c):04X} {unicodedata.name(c, '?')}" for c in bad})
    f["Invisible Unicode"] = [f"{len(bad)} char(s): " + "; ".join(seen)] if bad else []

    return {"pages": len(r.pages), "bytes": len(raw), "findings": f, "text": text}


if __name__ == "__main__":
    for p in (Path(a) for a in sys.argv[1:]):
        res = audit(p)
        print(f"\n{'='*72}\n{p.name}  ({res['bytes']:,} bytes, {res['pages']} page(s))\n{'='*72}")
        for v in VECTORS:
            hits = res["findings"][v]
            if hits:
                print(f"  [FOUND] {v}")
                for h in hits:
                    print(f"          - {h}")
            else:
                print(f"  [clean] {v}")
