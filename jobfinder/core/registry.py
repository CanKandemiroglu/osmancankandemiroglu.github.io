"""registry/sources.csv <-> sources table. The CSV is the editable truth; the DB mirrors it
and adds last_checked / robots_allows results, which are written back on save."""
from __future__ import annotations
import csv
from pathlib import Path

COLUMNS = ["id", "name", "country", "category", "url", "platform", "tenant_id",
           "robots_allows", "block_reason", "active", "last_checked", "notes"]


class RegistryError(ValueError):
    pass


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (rdr.fieldnames or [])]
        if missing:
            raise RegistryError(f"{path}: missing columns {missing}")
        rows = [{c: (r.get(c) or "").strip() for c in COLUMNS} for r in rdr]
    ids = [r["id"] for r in rows]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise RegistryError(f"{path}: duplicate ids {sorted(dupes)}")
    return rows


def validate(rows: list[dict]) -> list[tuple[str, str]]:
    """Return (id, problem) for rows that cannot be used as-is. They are still loaded, inactive."""
    problems = []
    for r in rows:
        if not r["id"] or not r["name"]:
            problems.append((r["id"] or "?", "id/name empty"))
        if r["active"] == "1" and not r["url"].startswith("http"):
            problems.append((r["id"], "active but no confirmed http(s) url"))
        if r["active"] not in ("0", "1"):
            problems.append((r["id"], f"active must be 0/1, got {r['active']!r}"))
    return problems


def load_into_db(con, path: Path) -> tuple[int, list[tuple[str, str]]]:
    rows = read_csv(path)
    problems = validate(rows)
    bad = {p[0] for p in problems}
    for r in rows:
        active = 0 if r["id"] in bad else int(r["active"])
        block = r["block_reason"] or ("registry validation failed" if r["id"] in bad else "")
        con.execute(
            "INSERT INTO sources(id,name,country,category,url,platform,tenant_id,robots_allows,block_reason,"
            "active,last_checked,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
            "name=excluded.name, country=excluded.country, category=excluded.category, url=excluded.url, "
            "platform=excluded.platform, tenant_id=excluded.tenant_id, "
            "robots_allows=CASE WHEN excluded.robots_allows='never' THEN 'never' "
            "  WHEN sources.robots_allows IN ('yes','no') AND excluded.robots_allows='' THEN sources.robots_allows "
            "  ELSE excluded.robots_allows END, "
            "block_reason=excluded.block_reason, active=excluded.active, notes=excluded.notes",
            (r["id"], r["name"], r["country"], r["category"], r["url"], r["platform"], r["tenant_id"],
             r["robots_allows"], block, active, r["last_checked"] or None, r["notes"]))
    con.commit()
    return len(rows), problems


def write_back(con, path: Path) -> None:
    """Write last_checked and the robots verdict back into the CSV, keeping row order."""
    rows = read_csv(path)
    db = {r["id"]: r for r in con.execute("SELECT * FROM sources").fetchall()}
    for r in rows:
        d = db.get(r["id"])
        if d:
            r["last_checked"] = d["last_checked"] or r["last_checked"]
            if r["robots_allows"] != "never":
                r["robots_allows"] = d["robots_allows"] or r["robots_allows"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
