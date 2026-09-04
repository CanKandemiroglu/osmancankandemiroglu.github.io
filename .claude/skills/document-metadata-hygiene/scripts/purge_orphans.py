#!/usr/bin/env python3
"""Blank orphaned Info dictionaries left behind by pypdf's clone_from.

PdfWriter(clone_from=...) copies every object in the source, including the
original /Info dictionary.  add_metadata({}) then creates a *new*, empty Info
object and points the trailer at it -- but the original is still in the file,
byte for byte, merely unreferenced.  `strings file.pdf` finds it instantly, so
the file still names the machine and toolchain that built it.

This rewrites the body of any such dictionary with spaces, keeping the object's
total byte length identical so every cross-reference offset stays valid.

A note on how this is implemented, because the obvious version is wrong.  The
tempting approach is one regex over the whole file:

    re.compile(rb"(\\d+\\s+\\d+\\s+obj\\s*<<)(.*?)(>>\\s*endobj)", re.S)

That silently fails.  Stream objects are `N 0 obj << ... >> stream ... endstream
endobj`, so the non-greedy body runs past the dictionary's own `>>`, through the
binary stream, and on to some *later* object's `endobj` -- swallowing any Info
dict that happened to sit in between.  The swallowed region then contains
/Filter, the "is this structural?" check says yes, and the leak is reported
clean.  Observed in practice: a HeadlessChrome Creator string survived a run
that printed "no orphaned metadata objects".

So: walk real object boundaries, and stop a dictionary at `stream` if one
follows.
"""

import re
import sys

# Keys that mark a dictionary as authoring metadata rather than document structure.
META_KEYS = (b"/Producer", b"/Creator", b"/CreationDate", b"/ModDate", b"/Author")
# Keys that mean "this is a real structural object, leave it alone".
STRUCT_KEYS = (b"/Type", b"/Subtype", b"/Kids", b"/Contents", b"/MediaBox", b"/Filter", b"/Length")

HEADER = re.compile(rb"(?<![0-9])(\d+)\s+(\d+)\s+obj\b")


def _dict_body(raw, start):
    """Given the offset just past an `N G obj` header, return (s, e) of the top
    level dictionary body, or None.  Stops before any stream data."""
    n = len(raw)
    i = start
    while i < n and raw[i : i + 1].isspace():
        i += 1
    if raw[i : i + 2] != b"<<":
        return None
    depth = 0
    j = i
    while j < n - 1:
        two = raw[j : j + 2]
        if two == b"<<":
            depth += 1
            j += 2
            continue
        if two == b">>":
            depth -= 1
            j += 2
            if depth == 0:
                return (i + 2, j - 2)
            continue
        if raw[j : j + 1] == b"(":  # skip literal string, honouring escapes
            j += 1
            par = 1
            while j < n and par:
                c = raw[j : j + 1]
                if c == b"\\":
                    j += 2
                    continue
                if c == b"(":
                    par += 1
                elif c == b")":
                    par -= 1
                j += 1
            continue
        j += 1
    return None


def purge(path, verbose=True, dry_run=False):
    raw = bytearray(open(path, "rb").read())
    flat = bytes(raw)
    hits = []

    for m in HEADER.finditer(flat):
        span = _dict_body(flat, m.end())
        if not span:
            continue
        s, e = span
        body = flat[s:e]
        if not any(k in body for k in META_KEYS):
            continue
        if any(k in body for k in STRUCT_KEYS):
            continue
        if len(body) > 4000:
            continue
        hits.append((m.group(1).decode(), bytes(body)))
        if not dry_run:
            raw[s:e] = b" " * (e - s)

    if hits and not dry_run:
        open(path, "wb").write(bytes(raw))

    if verbose:
        if hits:
            verb = "would blank" if dry_run else "blanked"
            print(f"{path}: {verb} {len(hits)} orphaned metadata object(s)")
            for num, h in hits:
                one = b" ".join(h.split())[:220].decode("latin-1", "replace")
                print(f"    obj {num}: {one}")
        else:
            print(f"{path}: no orphaned metadata objects")
    return len(hits)


def verify(path, needles=(b"HeadlessChrome", b"Skia", b"XeTeX", b"xdvipdfmx", b"Microsoft", b"/Producer")):
    """Independent check: these strings should not survive anywhere in the file."""
    raw = open(path, "rb").read()
    found = {n.decode(): raw.count(n) for n in needles if raw.count(n)}
    return found


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    dry = "--dry-run" in sys.argv
    if not args:
        sys.exit(__doc__)
    for p in args:
        purge(p, dry_run=dry)
        left = verify(p)
        if left:
            print(f"    STILL PRESENT in bytes: {left}")
