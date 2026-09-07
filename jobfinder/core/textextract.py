"""Turn an HTML ad page into plain text for the matcher. Generic; adapters may override."""
from __future__ import annotations
from bs4 import BeautifulSoup
from core.util import clean_text

DROP = ["script", "style", "nav", "header", "footer", "noscript", "svg", "form", "aside"]


def html_to_text(html: str, selectors: tuple[str, ...] = ("main", "article", "#content", ".content", "body")) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for t in soup(DROP):
        t.decompose()
    node = None
    for sel in selectors:
        node = soup.select_one(sel)
        if node and len(node.get_text(strip=True)) > 200:
            break
    node = node or soup
    for br in node.find_all(["br", "p", "li", "h1", "h2", "h3", "h4", "tr", "div"]):
        br.append("\n")
    return clean_text(node.get_text(" "))
