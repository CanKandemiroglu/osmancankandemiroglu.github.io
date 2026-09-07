"""PeopleAdmin applicant portals (e.g. jobs.uri.edu). Verified 2026-09-07 on URI.

Start at the confirmed root URL, follow the site's own 'Search Jobs' link (href contains
/postings/search), then the pagination links it declares (?page=N). Nothing is constructed.
Listing item: .job-item with title link /postings/{id}, then posting number, department,
position type, open date, close date.
"""
from __future__ import annotations
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from adapters.base import Posting, AdapterError
from core.util import parse_date, clean_text
from core.textextract import html_to_text


def _parse_listing(html: str, base: str):
    soup = BeautifulSoup(html, "lxml")
    items = soup.select(".job-item")
    out = []
    for it in items:
        a = it.find("a", href=re.compile(r"/postings/\d+"))
        if not a:
            continue
        url = urljoin(base, a["href"])
        pid = re.search(r"/postings/(\d+)", url).group(1)
        cells = [clean_text(c.get_text(" ")) for c in it.select(".col-md-2, .col-md-3, .col-md-4, .col-md-6, [class*=col-]")]
        cells = [c for c in cells if c and c not in ("View Details", "Bookmark")]
        dates = [parse_date(c, dayfirst=False) for c in cells if re.fullmatch(r"\d{2}/\d{2}/\d{4}", c)]
        dept = ""
        for c in cells[1:]:
            if not re.fullmatch(r"[A-Z]{1,3}\d{4,}", c) and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", c) \
                    and c != clean_text(a.get_text()) and "Staff" not in c and "Faculty" not in c:
                dept = c
                break
        ptype = next((c for c in cells if "Staff" in c or "Faculty" in c), "")
        out.append(Posting(external_id=pid, title=clean_text(a.get_text()), institution=dept,
                           location=ptype, url=url,
                           posted_date=dates[0] if dates else None,
                           deadline=dates[1] if len(dates) > 1 else None))
    next_links = sorted({urljoin(base, x["href"]) for x in soup.find_all("a", href=re.compile(r"[?&]page=\d+"))})
    return out, next_links


def list_postings(source, fetcher, config):
    root = fetcher.get(source["url"])
    if not root.ok:
        raise AdapterError(f"root fetch failed: status={root.status} error={root.error}")
    soup = BeautifulSoup(root.text, "lxml")
    a = soup.find("a", href=re.compile(r"/postings/search/?$"))
    if not a:
        raise AdapterError("no '/postings/search' link declared on the root page - not PeopleAdmin?")
    url = urljoin(root.final_url or source["url"], a["href"])
    seen_pages, out, ids = set(), [], set()
    queue = [url]
    while queue and len(seen_pages) < config.max_pages:
        u = queue.pop(0)
        if u in seen_pages:
            continue
        seen_pages.add(u)
        res = fetcher.get(u)
        if not res.ok:
            raise AdapterError(f"listing fetch failed: status={res.status} error={res.error}")
        items, nxt = _parse_listing(res.text, res.final_url or u)
        for p in items:
            if p.external_id not in ids:
                ids.add(p.external_id)
                out.append(p)
        for n in nxt:
            m = re.search(r"page=(\d+)", n)
            if n not in seen_pages and m and int(m.group(1)) <= config.max_pages:
                queue.append(n)
    return out


def fetch_detail(posting, fetcher, config) -> str:
    res = fetcher.get(posting["url"])
    if not res.ok:
        return ""
    soup = BeautifulSoup(res.text, "lxml")
    parts = []
    for th in soup.select("th"):
        td = th.find_next("td")
        if td:
            parts.append(f"{clean_text(th.get_text())}: {clean_text(td.get_text(' '))}")
    return "\n".join(parts) if parts else html_to_text(res.text)
