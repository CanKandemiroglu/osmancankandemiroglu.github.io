"""EURAXESS jobs listing (server-rendered Drupal). Verified 2026-09-07.

Listing: article.ecl-content-item -> h3 a[href^=/jobs/{id}], primary meta = organisation and
'Posted on: <date>', secondary meta labels (Department, Work Locations, Research Field,
Application Deadline where present). Pagination links are declared as ?page=N (0-based).
The listing is newest-first; we read config.max_pages pages per run.
"""
from __future__ import annotations
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from adapters.base import Posting, AdapterError
from core.util import parse_date, clean_text
from core.textextract import html_to_text

_FIELD = re.compile(r"(Department|Work Locations|Research Field|Application Deadline|Positions|Researcher Profile)\s*:", re.I)


def _parse(html: str, base: str):
    soup = BeautifulSoup(html, "lxml")
    out = []
    for art in soup.select("article.ecl-content-item"):
        a = art.select_one("h3 a[href]")
        if not a:
            continue
        url = urljoin(base, a["href"])
        m = re.search(r"/jobs/(\d+)", url)
        if not m:
            continue
        metas = [clean_text(li.get_text(" ")) for li in art.select(".ecl-content-block__primary-meta-item")]
        inst = metas[0] if metas else ""
        posted = next((parse_date(x.split(":", 1)[1]) for x in metas if x.lower().startswith("posted on")), None)
        desc = art.select_one(".ecl-content-block__description")
        sec = clean_text(" ".join(li.get_text(" ") for li in art.select(".ecl-content-block__secondary-meta-item")))
        fields = {}
        parts = _FIELD.split(sec)
        for i in range(1, len(parts) - 1, 2):
            fields[parts[i].lower()] = clean_text(parts[i + 1])
        loc = fields.get("work locations", "")
        country = ""
        cm = re.search(r"Number of offers:\s*\d+,\s*([^,]+)", loc)
        if cm:
            country = cm.group(1).strip()
        out.append(Posting(external_id=m.group(1), title=clean_text(a.get_text()), institution=inst,
                           location=loc[:200], url=url, posted_date=posted,
                           deadline=parse_date(fields.get("application deadline", "")),
                           body_text=(clean_text(desc.get_text(" ")) if desc else "") + "\n" + sec,
                           country=country, extra=fields))
    return out


def list_postings(source, fetcher, config):
    """Pagination uses the 'newest first' link the page itself declares
    (sort[name]=created&sort[direction]=DESC) plus &page=N.
    Observed 2026-09-07: the origin honours `page` only when an Accept-Language header is sent
    (the fetcher always sends one), and CloudFront caches a URL for 300 s keyed without that
    header - so a page can come back as page 0 if a header-less client cached it first.
    We therefore stop as soon as a page brings no new ids instead of fetching duplicates."""
    out, ids = [], set()
    url = source["url"]
    for page in range(config.max_pages):
        u = url if page == 0 else f"{url}{'&' if '?' in url else '?'}page={page}"
        res = fetcher.get(u)
        if not res.ok:
            if page == 0:
                raise AdapterError(f"listing fetch failed: status={res.status} error={res.error}")
            break
        items = _parse(res.text, res.final_url or u)
        if not items:
            if page == 0:
                raise AdapterError("no article.ecl-content-item on the listing page - layout changed?")
            break
        if page == 0:
            m = re.search(r'href="([^"]*sort%5Bname%5D=created[^"]*DESC[^"]*)"', res.text)
            if m:
                url = urljoin(u, m.group(1).replace("&amp;", "&"))
        added = 0
        for p in items:
            if p.external_id not in ids:
                ids.add(p.external_id)
                out.append(p)
                added += 1
        if added == 0 and page > 0:
            break
        if not re.search(rf"[?&]page={page + 1}\b", res.text):
            break
    return out


def fetch_detail(posting, fetcher, config) -> str:
    res = fetcher.get(posting["url"])
    if not res.ok:
        return ""
    text = html_to_text(res.text)
    return text


def deadline_from_detail(text: str):
    m = re.search(r"Application Deadline\s*\n?\s*([0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})", text)
    return parse_date(m.group(1)) if m else None
