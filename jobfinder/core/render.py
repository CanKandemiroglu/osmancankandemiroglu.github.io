"""queue.md (<=5 items), positions.md (everything, phone-readable), dashboard.html (local)."""
from __future__ import annotations
import html
import json
from datetime import date
from pathlib import Path

from core.rank import rank


def _md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def _dl(row, today):
    d = row.get("deadline")
    if not d:
        return "—", ""
    left = (d - today).days
    return d.isoformat(), f"{left} d"


def _flags(row) -> list[str]:
    f = []
    if row.get("repost"):
        f.append("REPOST")
    if row.get("manual"):
        f.append("MANUAL")
    for g in row.get("gates_unknown") or []:
        f.append(f"GATE? {g}")
    return f


def render_queue(rows: list[dict], manual_sources: list[dict], today: date, path: Path, new_only=True) -> str:
    cand = [r for r in rows if r["status"] == "open" and r["verdict"] in ("GO", "STRETCH")]
    if new_only:
        cand = [r for r in cand if r.get("is_new")]
    cand = rank(cand)[:5]
    lines = [f"# queue — {today.isoformat()}", ""]
    if not cand:
        lines.append("nothing today")
    for r in cand:
        d, left = _dl(r, today)
        lines += [f"## {_md_escape(r['title'])}",
                  "- " + " · ".join(x for x in (f"**{_md_escape(r.get('institution'))}**" if r.get('institution') else "", r.get('country') or "", r.get('source_name') or "") if x),
                  f"- deadline: {d} {('(' + left + ' left)') if left else ''}".rstrip(),
                  f"- verdict: **{r['verdict']}** — {r.get('reason') or ''}"]
        absent = r.get("absent") or []
        lines.append("- ABSENT: " + ("; ".join(_md_escape(a) for a in absent) if absent else "none"))
        fl = _flags(r)
        if fl:
            lines.append("- flags: " + ", ".join(fl))
        lines += [f"- {r['url']}", ""]
    if manual_sources:
        lines += ["", "## open yourself (robots.txt or no feed)", ""]
        lines += [f"- [{_md_escape(s['name'])}]({s['url']})" for s in manual_sources if s.get("url")]
    text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")
    return text


def render_positions(rows: list[dict], manual_sources: list[dict], today: date, path: Path) -> str:
    open_rows = rank([r for r in rows if r["status"] == "open" and r["verdict"] != "NO-GO"])
    nogo_rows = rank([r for r in rows if r["status"] == "open" and r["verdict"] == "NO-GO"])
    expired = rank([r for r in rows if r["status"] != "open"])
    hdr = ["| deadline | days left | verdict | title | institution | country | flags |",
           "|---|---|---|---|---|---|---|"]

    def line(r):
        d, left = _dl(r, today)
        return (f"| {d} | {left} | {r['verdict']} | [{_md_escape(r['title'])}]({r['url']}) | "
                f"{_md_escape(r.get('institution') or '')} | {r.get('country') or ''} | {', '.join(_flags(r))} |")

    out = [f"# open positions — {today.isoformat()}", "",
           f"{len(open_rows)} open (GO/STRETCH), {len(nogo_rows)} open NO-GO, {len(expired)} expired/gone.", ""]
    out += hdr + [line(r) for r in open_rows]
    if manual_sources:
        out += ["", "## sources to open yourself", ""]
        out += [f"- [{_md_escape(s['name'])}]({s['url']}) — {s.get('block_reason') or s.get('platform')}"
                for s in manual_sources if s.get("url")]
    if nogo_rows:
        out += ["", "<details><summary>open but NO-GO (" + str(len(nogo_rows)) + ")</summary>", ""]
        out += hdr + [line(r) for r in nogo_rows] + ["", "</details>"]
    out += ["", "<details><summary>expired / gone (" + str(len(expired)) + ")</summary>", ""]
    out += hdr + [line(r) for r in expired] + ["", "</details>", ""]
    text = "\n".join(out)
    path.write_text(text, encoding="utf-8")
    return text


DASH_CSS = """
body{font:14px/1.4 system-ui,sans-serif;margin:1.5rem;color:#222;background:#fff}
table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #ddd;padding:.35rem .5rem;text-align:left;vertical-align:top}
th{cursor:pointer;background:#f3f3f3;position:sticky;top:0}tr.expired td{color:#999}tr.GO td.v{color:#0a7a2f;font-weight:600}
tr.STRETCH td.v{color:#b26b00;font-weight:600}tr.NO-GO td.v{color:#999}.tag{display:inline-block;padding:0 .35rem;border-radius:3px;font-size:12px;margin-right:.2rem}
.REPOST{background:#ffe9a8}.MANUAL{background:#dbe9ff}.GATE{background:#ffd6d6}details{margin:.3rem 0}summary{cursor:pointer;color:#555}
.absent{color:#a00}.small{font-size:12px;color:#666}
"""
DASH_JS = """
document.querySelectorAll('th[data-k]').forEach(th=>th.addEventListener('click',()=>{
 const t=th.closest('table'),tb=t.tBodies[0],k=th.dataset.k,i=[...th.parentNode.children].indexOf(th);
 const asc=!(th.dataset.asc==='1');[...t.tHead.rows[0].cells].forEach(c=>c.dataset.asc='');th.dataset.asc=asc?'1':'0';
 [...tb.rows].sort((a,b)=>{let x=a.cells[i].dataset.s||a.cells[i].textContent,y=b.cells[i].dataset.s||b.cells[i].textContent;
 if(k==='n'){x=+x||1e18;y=+y||1e18}return (x>y?1:x<y?-1:0)*(asc?1:-1)}).forEach(r=>tb.appendChild(r));}));
"""


def render_dashboard(rows: list[dict], manual_sources: list[dict], today: date, path: Path, run_info: dict) -> str:
    rows = rank(rows)

    def tr(r):
        d, left = _dl(r, today)
        cls = f"{r['verdict']} {'expired' if r['status'] != 'open' else ''}"
        tags = "".join(f'<span class="tag {t.split()[0].replace("?","")}">{html.escape(t)}</span>' for t in _flags(r))
        absent = r.get("absent") or []
        ev = r.get("evidence") or []
        det = "".join(f"<li>[{html.escape(e['tier'])}] {html.escape(e['requirement'])} — <i>{html.escape(e['evidence'])}</i></li>"
                      for e in ev)
        gates = "; ".join(f"{g['name']}={g['status']}" for g in (r.get("gates") or []))
        return (f'<tr class="{cls}"><td data-s="{d}">{d}</td><td data-s="{(r["deadline"]-today).days if r.get("deadline") else ""}">{left}</td>'
                f'<td class="v">{html.escape(r["verdict"])}</td>'
                f'<td><a href="{html.escape(r["url"])}">{html.escape(r["title"])}</a><div class="small">{html.escape(r.get("reason") or "")} · gates: {html.escape(gates)}</div>'
                f'{"<div class=absent>ABSENT: " + html.escape("; ".join(absent)) + "</div>" if absent else ""}'
                f'{"<details><summary>evidence (" + str(len(ev)) + ")</summary><ul>" + det + "</ul></details>" if ev else ""}</td>'
                f'<td>{html.escape(r.get("institution") or "")}</td><td>{html.escape(r.get("country") or "")}</td>'
                f'<td>{html.escape(r.get("source_name") or "")}</td><td>{tags}</td><td>{r["status"]}</td></tr>')

    body = [f"<!doctype html><meta charset=utf-8><title>jobfinder {today}</title><style>{DASH_CSS}</style>",
            f"<h1>jobfinder — {today.isoformat()}</h1>",
            f"<p class=small>run: {html.escape(json.dumps(run_info))}</p>",
            "<table><thead><tr>"
            '<th data-k="s">deadline</th><th data-k="n">days</th><th data-k="s">verdict</th><th data-k="s">title</th>'
            '<th data-k="s">institution</th><th data-k="s">country</th><th data-k="s">source</th><th>flags</th><th data-k="s">status</th>'
            "</tr></thead><tbody>"]
    body += [tr(r) for r in rows]
    body.append("</tbody></table>")
    if manual_sources:
        body.append("<h2>open yourself</h2><ul>" + "".join(
            f'<li><a href="{html.escape(s["url"])}">{html.escape(s["name"])}</a> <span class=small>{html.escape(s.get("block_reason") or "")}</span></li>'
            for s in manual_sources if s.get("url")) + "</ul>")
    body.append(f"<script>{DASH_JS}</script>")
    text = "\n".join(body)
    path.write_text(text, encoding="utf-8")
    return text
