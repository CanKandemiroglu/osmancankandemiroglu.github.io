"""CSIC Sede Electronica - convocatorias de personal. Verified 2026-09-07.

Listing links: a[href*='/convocatorias-de-personal/convocatoria/{ref}'] with text
'<title> (Ref.NNNNN)'; pagination declared as ?page=N. Detail page fields (label | value text):
Estado, Tipo, Subtipo, Fecha de publicacion, Numero de plazas, Plazo de presentacion, Descripcion.
The deadline is usually expressed as 'N dias habiles a partir del siguiente al DD-MM-YYYY' and is
NOT converted to a calendar date here (business-day rules vary) - the phrase is kept in the body.
"""
from __future__ import annotations
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from adapters.base import Posting, AdapterError
from core.util import parse_date, clean_text
from core.textextract import html_to_text

LINK = re.compile(r"/convocatorias-de-personal/convocatoria/(\d+)")


def _parse(html: str, base: str):
    soup = BeautifulSoup(html, "lxml")
    out, seen = [], set()
    for a in soup.find_all("a", href=LINK):
        ref = LINK.search(a["href"]).group(1)
        if ref in seen:
            continue
        seen.add(ref)
        title = clean_text(a.get_text(" "))
        title = re.sub(r"\s*\(Ref\.\s*\d+\)\s*$", "", title)
        out.append(Posting(external_id=ref, title=title, institution="CSIC", url=urljoin(base, a["href"]),
                           country="ES", extra={"ref": ref}))
    return out


def list_postings(source, fetcher, config):
    out, ids = [], set()
    for pg in range(config.max_pages):
        u = source["url"] if pg == 0 else f"{source['url']}?page={pg}"
        res = fetcher.get(u)
        if not res.ok:
            if pg == 0:
                raise AdapterError(f"listing fetch failed: status={res.status} error={res.error}")
            break
        items = _parse(res.text, res.final_url or u)
        if not items:
            if pg == 0:
                raise AdapterError("no convocatoria links found on the listing page")
            break
        for p in items:
            if p.external_id not in ids:
                ids.add(p.external_id)
                out.append(p)
        if not re.search(rf"[?&]page={pg + 1}\b", res.text):
            break
    return out


def fetch_detail(posting, fetcher, config) -> str:
    res = fetcher.get(posting["url"])
    if not res.ok:
        return ""
    text = html_to_text(res.text)
    return text


def posted_from_detail(text: str):
    m = re.search(r"Fecha de publicaci[oó]n\s*\n?\s*\w*,?\s*(\d{2}/\d{2}/\d{4})", text)
    return parse_date(m.group(1)) if m else None
