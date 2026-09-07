"""Any RSS/Atom feed whose URL is confirmed (declared by the site itself). feedparser."""
from __future__ import annotations
import re
import feedparser
from bs4 import BeautifulSoup
from adapters.base import Posting, AdapterError
from core.util import parse_date, clean_text
from core.textextract import html_to_text


def list_postings(source, fetcher, config):
    res = fetcher.get(source["url"])
    if not res.ok:
        raise AdapterError(f"feed fetch failed: status={res.status} error={res.error}")
    feed = feedparser.parse(res.content)
    if feed.bozo and not feed.entries:
        raise AdapterError(f"not a parseable feed: {feed.bozo_exception}")
    out = []
    for e in feed.entries:
        link = e.get("link") or ""
        eid = e.get("id") or link
        if not eid:
            continue
        title = clean_text(e.get("title", ""))
        inst = ""
        # AGU/Madgex style "Employer: Title"; EGU style "Title | Country | Type"
        if ":" in title and title.index(":") < 60 and "|" not in title:
            inst, title = [x.strip() for x in title.split(":", 1)]
        loc = ""
        if "|" in title:
            parts = [x.strip() for x in title.split("|")]
            title, loc = parts[0], parts[1] if len(parts) > 1 else ""
        ssoup = BeautifulSoup(e.get("summary", "") or "", "lxml")
        summary = ssoup.get_text(" ", strip=True)
        if not inst:
            b = ssoup.find("b")
            if b and len(b.get_text(strip=True)) < 120:
                inst = clean_text(b.get_text()).split(",")[0]
        published = parse_date(e.get("published") or e.get("updated"), dayfirst=True)
        m = re.search(r"\d{1,2}\s+[A-Za-z]{3}\s+\d{4}", e.get("published", "") or "")
        if m:
            published = parse_date(m.group(0))
        out.append(Posting(external_id=re.sub(r"[?#].*$", "", eid)[-120:], title=title, institution=inst,
                           location=loc, url=link, posted_date=published, body_text=summary[:2000],
                           country=source.get("country", "")))
    return out


def fetch_detail(posting, fetcher, config) -> str:
    res = fetcher.get(posting["url"])
    return html_to_text(res.text) if res.ok else ""
