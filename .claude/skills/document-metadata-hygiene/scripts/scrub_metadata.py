#!/usr/bin/env python3
"""Strip authoring/tooling metadata from documents you own.

Removes producer, creator, author, company and timestamp fields that leak the
software and machine that generated a file. Content, layout and rendering are
left byte-identical wherever the format allows.

Deliberately preserved (see PRESERVED below): C2PA / Content Credentials,
ICC colour profiles, and anything required to render the file correctly.

Usage:
    scrub_metadata.py FILE [FILE ...] [-o OUTDIR] [--inspect] [--suffix S]

    --inspect   report what would be removed; write nothing
    -o OUTDIR   write cleaned files here (default: alongside, with suffix)
    --suffix S  suffix for output names (default: ".clean")
    --in-place  overwrite the input files
"""

from __future__ import annotations

import argparse
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path

# So `from purge_orphans import purge` works however this script is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Segments/boxes this tool never strips. C2PA is a provenance signal: removing
# it is out of scope for metadata hygiene and is not what this script is for.
PRESERVED = {
    "jpeg": "APP0 (JFIF), APP2 (ICC profile), APP11 (JUMBF/C2PA)",
    "png": "iCCP (ICC profile), sRGB, gAMA, cHRM, and all critical chunks",
    "pdf": "page content, fonts, structure; any C2PA attachment",
}

PDF_INFO_KEYS = (
    "/Title", "/Author", "/Subject", "/Keywords",
    "/Creator", "/Producer", "/CreationDate", "/ModDate", "/Trapped",
)

OOXML_PROPS = ("docProps/core.xml", "docProps/app.xml", "docProps/custom.xml")

# OOXML core.xml fields worth clearing. Everything else in core.xml is left be.
OOXML_CORE_FIELDS = (
    "dc:creator", "cp:lastModifiedBy", "cp:revision", "dc:title",
    "dc:subject", "dc:description", "cp:keywords", "cp:category",
    "dcterms:created", "dcterms:modified", "cp:lastPrinted",
    "cp:contentStatus", "dc:language", "dc:identifier",
)
OOXML_APP_FIELDS = (
    "Application", "AppVersion", "Company", "Manager", "Template",
    "TotalTime", "LastAuthor", "PresentationFormat",
)


def _fmt(n: int) -> str:
    return f"{n:,} bytes"


# ---------------------------------------------------------------- PDF


def scrub_pdf(src: Path, dst: Path | None, inspect: bool) -> list[str]:
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import NameObject
    except ImportError:
        raise RuntimeError("PDF support needs pypdf:  pip install pypdf")

    reader = PdfReader(str(src))
    found = []
    meta = reader.metadata or {}
    for k, v in meta.items():
        if v:
            found.append(f"Info {k} = {str(v)[:90]}")
    if NameObject("/Metadata") in reader.trailer["/Root"]:
        found.append("XMP metadata packet (/Metadata)")

    if inspect or dst is None:
        return found

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    root = writer._root_object
    if NameObject("/Metadata") in root:
        del root[NameObject("/Metadata")]
    writer.add_metadata({})
    if getattr(writer, "_info", None) is not None:
        try:
            writer._info.get_object().clear()
        except Exception:
            pass
    with open(dst, "wb") as fh:
        writer.write(fh)

    # pypdf writes a fresh empty Info object and repoints the trailer, but any
    # Info dictionary carried over from the source survives in the file as an
    # unreferenced object.  pypdf then reports the metadata as empty while
    # `strings` still shows the toolchain name.  Blank those too, and blank the
    # trailer's /Info reference, before anyone calls this file clean.
    try:
        from purge_orphans import purge

        n = purge(str(dst), verbose=False)
        if n:
            found.append(f"{n} orphaned Info object(s) left by clone/copy")
    except Exception as exc:  # pragma: no cover
        found.append(f"WARNING: orphan purge failed ({exc}) -- verify with `strings`")

    _blank_trailer_info(dst)

    leaks = _residual_toolchain_strings(dst)
    if leaks:
        found.append(f"WARNING: still present in raw bytes: {leaks}")

    return found


_TOOLCHAIN_NEEDLES = (
    b"HeadlessChrome", b"Skia/PDF", b"XeTeX", b"xdvipdfmx",
    b"Microsoft Office", b"LibreOffice", b"Chromium",
)


def _blank_trailer_info(path: Path) -> None:
    """Space out the trailer's /Info reference, preserving byte offsets."""
    raw = bytearray(path.read_bytes())
    i = raw.rfind(b"trailer")
    if i < 0:
        return
    m = re.search(rb"/Info\s+\d+\s+\d+\s+R", raw[i:])
    if m:
        s, e = i + m.start(), i + m.end()
        raw[s:e] = b" " * (e - s)
        path.write_bytes(bytes(raw))


def _residual_toolchain_strings(path: Path) -> dict:
    """Check the written bytes directly.  Never trust the library that wrote
    the file to tell you what is in it."""
    raw = path.read_bytes()
    return {n.decode(): raw.count(n) for n in _TOOLCHAIN_NEEDLES if n in raw}


# ---------------------------------------------------------------- OOXML


def _blank_xml_fields(xml: bytes, fields: tuple[str, ...]) -> tuple[bytes, list[str]]:
    removed = []
    for field in fields:
        pat = re.compile(
            rb"<" + re.escape(field.encode()) + rb"(\s[^>]*)?>(.*?)</"
            + re.escape(field.encode()) + rb">",
            re.S,
        )

        def repl(m, field=field, removed=removed):
            val = m.group(2).strip()
            if val:
                removed.append(f"{field} = {val.decode('utf-8', 'replace')[:90]}")
            return b""

        xml = pat.sub(repl, xml)
        # self-closing form
        xml = re.sub(rb"<" + re.escape(field.encode()) + rb"(\s[^>]*)?/>", b"", xml)
    return xml, removed


def scrub_ooxml(src: Path, dst: Path | None, inspect: bool) -> list[str]:
    found: list[str] = []
    with zipfile.ZipFile(src) as zin:
        names = zin.namelist()
        for part in OOXML_PROPS:
            if part not in names:
                continue
            data = zin.read(part)
            fields = OOXML_CORE_FIELDS if part.endswith("core.xml") else OOXML_APP_FIELDS
            if part.endswith("custom.xml"):
                found.append(f"{part} (custom properties, {_fmt(len(data))})")
                continue
            _, rem = _blank_xml_fields(data, fields)
            found += [f"{part}: {r}" for r in rem]

        if inspect or dst is None:
            return found

        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "docProps/custom.xml":
                    continue  # drop entirely
                data = zin.read(item.filename)
                if item.filename in ("docProps/core.xml", "docProps/app.xml"):
                    fields = (
                        OOXML_CORE_FIELDS
                        if item.filename.endswith("core.xml")
                        else OOXML_APP_FIELDS
                    )
                    data, _ = _blank_xml_fields(data, fields)
                # normalise timestamps in the zip directory too
                info = zipfile.ZipInfo(item.filename, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = item.external_attr
                zout.writestr(info, data)
    return found


# ---------------------------------------------------------------- PNG


PNG_STRIP = {b"tEXt", b"iTXt", b"zTXt", b"tIME", b"eXIf"}


def scrub_png(src: Path, dst: Path | None, inspect: bool) -> list[str]:
    data = src.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("not a PNG")
    out = bytearray(data[:8])
    found = []
    pos = 8
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos:pos + 12 + length]
        if ctype in PNG_STRIP:
            body = data[pos + 8:pos + 8 + length]
            found.append(f"{ctype.decode()} chunk ({_fmt(length)}): "
                         f"{body[:70].decode('utf-8', 'replace')!r}")
        else:
            out += chunk
        pos += 12 + length
        if ctype == b"IEND":
            break
    if not inspect and dst is not None:
        dst.write_bytes(bytes(out))
    return found


# ---------------------------------------------------------------- JPEG

# APP1 EXIF/XMP, APP13 IPTC/Photoshop, COM comments. APP0/APP2/APP11 kept.
JPEG_STRIP_MARKERS = {0xE1, 0xED, 0xEE, 0xFE}


def scrub_jpeg(src: Path, dst: Path | None, inspect: bool) -> list[str]:
    data = src.read_bytes()
    if data[:2] != b"\xff\xd8":
        raise RuntimeError("not a JPEG")
    out = bytearray(b"\xff\xd8")
    found = []
    pos = 2
    while pos < len(data) - 1:
        if data[pos] != 0xFF:
            out += data[pos:]
            break
        marker = data[pos + 1]
        if marker == 0xDA:  # start of scan: copy the rest verbatim
            out += data[pos:]
            break
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            out += data[pos:pos + 2]
            pos += 2
            continue
        (seglen,) = struct.unpack(">H", data[pos + 2:pos + 4])
        seg = data[pos:pos + 2 + seglen]
        if marker in JPEG_STRIP_MARKERS:
            name = "COM" if marker == 0xFE else f"APP{marker - 0xE0}"
            tag = data[pos + 4:pos + 4 + 20].split(b"\x00")[0]
            found.append(f"{name} ({_fmt(seglen)}) "
                         f"{tag.decode('utf-8', 'replace')!r}")
        else:
            out += seg
        pos += 2 + seglen
    if not inspect and dst is not None:
        dst.write_bytes(bytes(out))
    return found


HANDLERS = {
    ".pdf": scrub_pdf,
    ".docx": scrub_ooxml, ".xlsx": scrub_ooxml, ".pptx": scrub_ooxml,
    ".docm": scrub_ooxml, ".xlsm": scrub_ooxml, ".pptm": scrub_ooxml,
    ".png": scrub_png,
    ".jpg": scrub_jpeg, ".jpeg": scrub_jpeg,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("-o", "--outdir", type=Path)
    ap.add_argument("--suffix", default=".clean")
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument("--inspect", action="store_true")
    args = ap.parse_args()

    rc = 0
    for src in args.files:
        if not src.is_file():
            print(f"!! {src}: not a file", file=sys.stderr)
            rc = 1
            continue
        handler = HANDLERS.get(src.suffix.lower())
        if handler is None:
            print(f"-- {src.name}: unsupported type {src.suffix!r}, skipped")
            continue

        if args.inspect:
            dst = None
        elif args.in_place:
            dst = src.with_suffix(src.suffix + ".tmp")
        elif args.outdir:
            args.outdir.mkdir(parents=True, exist_ok=True)
            dst = args.outdir / src.name
        else:
            dst = src.with_name(src.stem + args.suffix + src.suffix)

        try:
            found = handler(src, dst, args.inspect)
        except Exception as exc:                        # noqa: BLE001
            print(f"!! {src.name}: {exc}", file=sys.stderr)
            rc = 1
            continue

        if args.in_place and dst is not None:
            shutil.move(str(dst), str(src))
            dst = src

        verb = "would remove" if args.inspect else "removed"
        print(f"\n{src.name}  [{src.suffix.lower().lstrip('.')}]")
        if found:
            for f in found:
                print(f"   {verb}: {f}")
        else:
            print(f"   nothing to remove — no authoring metadata present")
        kind = "jpeg" if src.suffix.lower() in (".jpg", ".jpeg") else src.suffix.lower().lstrip(".")
        if kind in PRESERVED:
            print(f"   preserved: {PRESERVED[kind]}")
        if not args.inspect and dst is not None:
            print(f"   -> {dst}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
