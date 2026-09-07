"""SQLite schema and small helpers. One file, no ORM."""
from __future__ import annotations
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

from core.util import now_iso, dedup_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT, category TEXT, url TEXT,
  platform TEXT, tenant_id TEXT, robots_allows TEXT, block_reason TEXT,
  active INTEGER NOT NULL DEFAULT 1, last_checked TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS postings(
  id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL REFERENCES sources(id),
  external_id TEXT NOT NULL, title TEXT NOT NULL, institution TEXT, location TEXT, url TEXT,
  posted_date TEXT, deadline TEXT, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
  body_text TEXT, dedup_hash TEXT, status TEXT NOT NULL DEFAULT 'open',
  country TEXT, detail_fetched INTEGER NOT NULL DEFAULT 0,
  UNIQUE(source_id, external_id));
CREATE INDEX IF NOT EXISTS ix_postings_hash ON postings(dedup_hash);
CREATE TABLE IF NOT EXISTS verdicts(
  posting_id INTEGER PRIMARY KEY REFERENCES postings(id), verdict TEXT NOT NULL,
  gates_failed TEXT, absent_json TEXT, evidence_json TEXT, scored_at TEXT, scorer TEXT);
CREATE TABLE IF NOT EXISTS reposts(
  dedup_hash TEXT, first_posting_id INTEGER, repeat_posting_id INTEGER, detected_at TEXT,
  UNIQUE(first_posting_id, repeat_posting_id));
CREATE TABLE IF NOT EXISTS outcomes(
  posting_id INTEGER REFERENCES postings(id), action TEXT NOT NULL, date TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, started TEXT, finished TEXT, sources_ok INTEGER,
  sources_failed INTEGER, new_postings INTEGER, errors_json TEXT);
CREATE TABLE IF NOT EXISTS robots_cache(
  host TEXT PRIMARY KEY, fetched_at TEXT, status INTEGER, body TEXT);
CREATE TABLE IF NOT EXISTS fetch_log(
  ts TEXT, run_id INTEGER, host TEXT, url TEXT, status INTEGER, bytes INTEGER,
  elapsed_ms INTEGER, error TEXT);
"""


def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    cols = {r[1] for r in con.execute('PRAGMA table_info(postings)')}
    if 'country' not in cols:
        con.execute('ALTER TABLE postings ADD COLUMN country TEXT')
    if 'detail_fetched' not in cols:
        con.execute('ALTER TABLE postings ADD COLUMN detail_fetched INTEGER NOT NULL DEFAULT 0')
    return con


def _d(v: Optional[date]) -> Optional[str]:
    return v.isoformat() if v else None


def start_run(con) -> int:
    cur = con.execute("INSERT INTO runs(started) VALUES(?)", (now_iso(),))
    con.commit()
    return cur.lastrowid


def finish_run(con, run_id: int, ok: int, failed: int, new: int, errors: list) -> None:
    con.execute("UPDATE runs SET finished=?, sources_ok=?, sources_failed=?, new_postings=?, "
                "errors_json=? WHERE id=?",
                (now_iso(), ok, failed, new, json.dumps(errors, ensure_ascii=False), run_id))
    con.commit()


def upsert_posting(con, source_id: str, p, today: date) -> tuple[int, bool]:
    """Insert or refresh a posting. Returns (posting_id, is_new)."""
    row = con.execute("SELECT id, body_text, deadline FROM postings WHERE source_id=? AND external_id=?",
                      (source_id, p.external_id)).fetchone()
    h = dedup_hash(p.title, p.institution)
    if row:
        con.execute(
            "UPDATE postings SET title=?, institution=?, location=?, url=?, posted_date=COALESCE(?,posted_date), "
            "deadline=COALESCE(?,deadline), last_seen=?, status='open', dedup_hash=?, country=COALESCE(NULLIF(?,''),country), "
            "body_text=CASE WHEN length(COALESCE(?,''))>length(COALESCE(body_text,'')) THEN ? ELSE body_text END "
            "WHERE id=?",
            (p.title, p.institution, p.location, p.url, _d(p.posted_date), _d(p.deadline),
             today.isoformat(), h, p.country, p.body_text, p.body_text, row["id"]))
        return row["id"], False
    cur = con.execute(
        "INSERT INTO postings(source_id, external_id, title, institution, location, url, posted_date, "
        "deadline, first_seen, last_seen, body_text, dedup_hash, status, country) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'open',?)",
        (source_id, p.external_id, p.title, p.institution, p.location, p.url, _d(p.posted_date),
         _d(p.deadline), today.isoformat(), today.isoformat(), p.body_text, h, p.country))
    return cur.lastrowid, True


def mark_gone(con, source_id: str, seen_ids: Iterable[str], today: date) -> int:
    """Postings of a successfully-listed source that were not in today's listing -> gone."""
    seen = set(seen_ids)
    rows = con.execute("SELECT id, external_id FROM postings WHERE source_id=? AND status='open'",
                       (source_id,)).fetchall()
    n = 0
    for r in rows:
        if r["external_id"] not in seen:
            con.execute("UPDATE postings SET status='gone' WHERE id=?", (r["id"],))
            n += 1
    return n


def expire_by_deadline(con, today: date) -> int:
    cur = con.execute("UPDATE postings SET status='expired' WHERE status='open' AND deadline IS NOT NULL "
                      "AND deadline < ?", (today.isoformat(),))
    return cur.rowcount


def detect_reposts(con, posting_id: int) -> Optional[int]:
    """A new posting whose dedup_hash matches an older, no-longer-open posting is a repost."""
    p = con.execute("SELECT dedup_hash, first_seen FROM postings WHERE id=?", (posting_id,)).fetchone()
    old = con.execute(
        "SELECT id FROM postings WHERE dedup_hash=? AND id<>? AND status IN ('expired','gone') "
        "AND first_seen < ? ORDER BY first_seen LIMIT 1",
        (p["dedup_hash"], posting_id, p["first_seen"])).fetchone()
    if not old:
        return None
    con.execute("INSERT OR IGNORE INTO reposts(dedup_hash, first_posting_id, repeat_posting_id, detected_at) "
                "VALUES(?,?,?,?)", (p["dedup_hash"], old["id"], posting_id, now_iso()))
    return old["id"]


def save_verdict(con, posting_id: int, verdict: str, gates_failed: list, absent: list,
                 evidence: list, scorer: str) -> None:
    con.execute(
        "INSERT OR REPLACE INTO verdicts(posting_id, verdict, gates_failed, absent_json, evidence_json, "
        "scored_at, scorer) VALUES(?,?,?,?,?,?,?)",
        (posting_id, verdict, json.dumps(gates_failed, ensure_ascii=False),
         json.dumps(absent, ensure_ascii=False), json.dumps(evidence, ensure_ascii=False), now_iso(), scorer))


def log_fetch(con, run_id, host, url, status, nbytes, elapsed_ms, error) -> None:
    con.execute("INSERT INTO fetch_log(ts, run_id, host, url, status, bytes, elapsed_ms, error) "
                "VALUES(?,?,?,?,?,?,?,?)", (now_iso(), run_id, host, url, status, nbytes, elapsed_ms, error))
