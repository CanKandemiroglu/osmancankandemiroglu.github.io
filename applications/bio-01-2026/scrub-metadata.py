#!/usr/bin/env python3
"""Scrub renderer fingerprints from a Chromium-produced PDF, in place.

Headless Chromium stamps its full user-agent into /Creator ("…
HeadlessChrome/141.0.0.0 …") and "Skia/PDF" into /Producer. Neither belongs
in a document that goes out with an application, so this rewrites the Info
dictionary with authored values.

The rewrite is byte-length-preserving: the new dictionary is padded with
spaces to the exact size of the old object, so every byte offset in the
cross-reference table stays valid and the file needs no xref surgery. The
Chromium output carries no XMP packet (checked below); if a future renderer
adds one, this refuses rather than leaving a half-scrubbed file.

Only stdlib — the export path needs nothing beyond Chromium and python3.

Usage: scrub-metadata.py FILE.pdf --author NAME [--subject TEXT]
                                  [--creator TEXT] [--producer TEXT]
"""
import argparse
import re
import sys


def pdf_string(text):
    """A PDF text string: ASCII stays literal, anything else goes UTF-16BE hex."""
    if all(32 <= ord(c) < 127 for c in text):
        escaped = text.replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')
        return b'(' + escaped.encode('ascii') + b')'
    return b'<FEFF' + text.encode('utf-16-be').hex().upper().encode('ascii') + b'>'


def incremental_rewrite(data, num, new_dict):
    """Append a new Info object as an incremental update (PDF 32000-1 §7.5.6)."""
    trailer = None
    for trailer in re.finditer(rb'trailer\s*<<(.*?)>>\s*startxref\s+(\d+)', data, re.S):
        pass  # the last trailer is the active one
    if trailer is None:
        sys.exit('error: no classic trailer; incremental update needs one '
                 '(cross-reference streams are not supported)')
    tdict, prev = trailer.group(1), int(trailer.group(2))
    size = re.search(rb'/Size\s+(\d+)', tdict)
    root = re.search(rb'/Root\s+(\d+\s+\d+\s+R)', tdict)
    if not size or not root:
        sys.exit('error: trailer is missing /Size or /Root')

    out = data if data.endswith(b'\n') else data + b'\n'
    obj_offset = len(out)
    out += b'%d 0 obj\n<<%s>>\nendobj\n' % (num, new_dict)
    xref_offset = len(out)
    out += b'xref\n%d 1\n%010d 00000 n \n' % (num, obj_offset)
    out += (b'trailer\n<</Size %d /Root %s /Info %d 0 R /Prev %d>>\n'
            b'startxref\n%d\n%%%%EOF\n'
            % (int(size.group(1)), root.group(1), num, prev, xref_offset))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--author', required=True)
    ap.add_argument('--subject', default=None)
    ap.add_argument('--creator', default=None)
    ap.add_argument('--producer', default=None)
    args = ap.parse_args()

    data = open(args.pdf, 'rb').read()

    if b'<?xpacket' in data:
        sys.exit('error: PDF carries an XMP packet; this scrubber only handles '
                 'the Info dictionary. Scrub XMP before shipping.')

    ref = None
    for ref in re.finditer(rb'/Info\s+(\d+)\s+(\d+)\s+R', data):
        pass  # the last trailer wins
    if ref is None:
        sys.exit('error: no /Info reference in trailer')
    num = int(ref.group(1))

    obj = re.search(rb'(?<![0-9])' + str(num).encode() + rb'\s+0\s+obj\s*<<(.*?)>>\s*endobj',
                    data, re.S)
    if obj is None:
        sys.exit(f'error: Info object {num} not found, or stored in an object stream')

    old_dict = obj.group(1)
    keep = {}
    for key in (b'Title', b'CreationDate', b'ModDate'):
        m = re.search(rb'/' + key + rb'\s*(\([^)]*\)|<[0-9A-Fa-f\s]*>)', old_dict)
        if m:
            keep[key] = m.group(1)

    entries = []
    if b'Title' in keep:
        entries.append(b'/Title ' + keep[b'Title'])
    entries.append(b'/Author ' + pdf_string(args.author))
    if args.subject:
        entries.append(b'/Subject ' + pdf_string(args.subject))
    if args.creator:
        entries.append(b'/Creator ' + pdf_string(args.creator))
    if args.producer:
        entries.append(b'/Producer ' + pdf_string(args.producer))
    for key in (b'CreationDate', b'ModDate'):
        if key in keep:
            entries.append(b'/' + key + b' ' + keep[key])

    new_dict = b'\n'.join(entries)
    if len(new_dict) <= len(old_dict):
        new_dict += b' ' * (len(old_dict) - len(new_dict))
        start, end = obj.span(1)
        out = data[:start] + new_dict + data[end:]
        how = 'in place'
    else:
        out = incremental_rewrite(data, num, new_dict)
        how = 'via incremental update'

    open(args.pdf, 'wb').write(out)
    print(f'scrubbed {args.pdf} ({how})')


if __name__ == '__main__':
    main()
