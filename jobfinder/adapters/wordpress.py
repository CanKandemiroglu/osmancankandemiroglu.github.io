"""Generic WordPress listing page (archive/tag page or a static 'vacancies' page).

Takes every <article> (WordPress theme convention) with a heading link; falls back to links
inside the main content area whose text looks like a vacancy title. Verified on the ICMAN
tag page (WordPress) on 2026-09-07; natur.gl uses the same platform per the report but was not
reachable from the build sandbox.
"""
from __future__ import annotations
import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from adapters.base import Posting, AdapterError
from core.util import parse_date, clean_text
from core.textextract import html_to_text


def list_postings(source, fetcher, config):
    res = fetcher.get(source["url"])
    if not res.ok:
        raise AdapterError(f"page fetch failed: status={res.status} error={res.error}")
    soup = BeautifulSoup(res.text, "lxml")
    base = res.final_url or source["url"]
    host = urlsplit(base).netloc
    out, seen = [], set()
    for art in soup.select("article"):
        a = art.select_one("h1 a[href], h2 a[href], h3 a[href], .entry-title a[href]")
        if not a:
            continue
        url = urljoin(base, a["href"])
        if url in seen or urlsplit(url).netloc != host:
            continue
        seen.add(url)
        t = art.find("time")
        posted = parse_date(t.get("datetime") or t.get_text()) if t else None
        excerpt = art.select_one(".entry-summary, .entry-content, p")
        out.append(Posting(external_id=urlsplit(url).path.strip("/")[-120:], title=clean_text(a.get_text()),
                           institution=source["name"], url=url, posted_date=posted,
                           body_text=clean_text(excerpt.get_text(" "))[:1500] if excerpt else "",
                           country=source.get("country", "")))
    if not out:
        main = soup.select_one("main, #main, #content, .entry-content, .content") or soup
        for a in main.find_all("a", href=True):
            url = urljoin(base, a["href"])
            txt = clean_text(a.get_text())
            if urlsplit(url).netloc != host or len(txt) < 12 or url in seen:
                continue
            if re.search(r"(phd|ph\.d|postdoc|stilling|stipendiat|position|vacanc|contrat|plaza|forsker|researcher)", txt, re.I):
                seen.add(url)
                out.append(Posting(external_id=urlsplit(url).path.strip("/")[-120:], title=txt,
                                   institution=source["name"], url=url, country=source.get("country", "")))
    return out


def fetch_detail(posting, fetcher, config) -> str:
    res = fetcher.get(posting["url"])
    return html_to_text(res.text, selectors=(".entry-content", "article", "main", "body")) if res.ok else ""
