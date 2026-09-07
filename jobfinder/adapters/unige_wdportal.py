"""Universite de Geneve bespoke 'wd_portal' (jobs.unige.ch). Verified 2026-09-07.

Root page declares a <meta http-equiv=refresh> to wd_portal.search_start; that page declares
links to wd_portal.search_results for the academic and admin categories. We follow the declared
links only. Each result is div.jobpost_body with h2 > a[href*=show_job], 'Delai d'inscription'
and 'Reference'. Pages are latin-1.
"""
from __future__ import annotations
import re
from urllib.parse import urljoin, urlsplit, parse_qs
from bs4 import BeautifulSoup
from adapters.base import Posting, AdapterError
from core.util import parse_date, clean_text
from core.textextract import html_to_text


def _text(res):
    return res.content.decode(res.encoding or "latin-1", errors="replace")


def _parse_results(html: str, base: str):
    soup = BeautifulSoup(html, "lxml")
    out = []
    for blk in soup.select("div.jobpost_body"):
        a = blk.find("a", href=re.compile(r"show_job"))
        if not a:
            continue
        url = urljoin(base, a["href"])
        pid = parse_qs(urlsplit(url).query).get("p_web_page_id", [""])[0]
        if not pid:
            continue
        section = blk.select_one(".section_\\/_division .jobvalue, .jobclass .jobvalue")
        deadline = blk.select_one(".date_off")
        ref = blk.select_one(".refno")
        dl = None
        if deadline:
            dl = parse_date(re.sub(r".*?:", "", deadline.get_text(" ", strip=True)))
        out.append(Posting(external_id=pid, title=clean_text(a.get_text()),
                           institution=clean_text(section.get_text(" ")) if section else "",
                           url=url, deadline=dl,
                           extra={"ref": clean_text(re.sub(r".*?:", "", ref.get_text(" "))) if ref else ""}))
    return out


def list_postings(source, fetcher, config):
    root = fetcher.get(source["url"])
    if not root.ok:
        raise AdapterError(f"root fetch failed: status={root.status} error={root.error}")
    live = re.sub(r"<!--.*?-->", "", root.text, flags=re.S)        # ignore commented-out redirects
    m = re.search(r'http-equiv="refresh"[^>]*url=([^">]+)', live, re.I)
    if not m:
        raise AdapterError("no meta-refresh declared on the root page")
    start = fetcher.get(urljoin(source["url"], m.group(1)))
    if not start.ok:
        raise AdapterError(f"search_start fetch failed: status={start.status} error={start.error}")
    soup = BeautifulSoup(_text(start), "lxml")
    links = sorted({urljoin(start.final_url or source["url"], a["href"])
                    for a in soup.find_all("a", href=re.compile(r"wd_portal\.search_results"))})
    if not links:
        raise AdapterError("search_start page declares no search_results links")
    out, ids = [], set()
    for u in links[:config.max_pages]:
        res = fetcher.get(u)
        if not res.ok:
            continue
        for p in _parse_results(_text(res), res.final_url or u):
            p.institution = p.institution or "Universite de Geneve"
            p.country = "CH"
            if p.external_id not in ids:
                ids.add(p.external_id)
                out.append(p)
    return out


def fetch_detail(posting, fetcher, config) -> str:
    res = fetcher.get(posting["url"])
    if not res.ok:
        return ""
    soup = BeautifulSoup(_text(res), "lxml")
    node = soup.select_one("div.job_detail") or soup
    return html_to_text(str(node), selectors=("div.job_detail", "body"))
