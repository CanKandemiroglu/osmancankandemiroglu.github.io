#!/usr/bin/env python3
"""The whole daily run: registry -> fetch (stage 1) -> gates -> keyword pre-filter -> stage 2 ->
score -> render -> verify -> sync."""
from __future__ import annotations
import argparse
import json
import logging
import os
import subprocess
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from adapters import get_adapter                      # noqa: E402
from core import db as dbm                            # noqa: E402
from core.config import load_config                   # noqa: E402
from core.fetch import Fetcher, BlockedHost           # noqa: E402
from core.gates import run_gates                      # noqa: E402
from core.match import score_keyword                  # noqa: E402
from core.profile import load_profile, ProfileMissing # noqa: E402
from core.registry import load_into_db, write_back    # noqa: E402
from core.render import render_queue, render_positions, render_dashboard  # noqa: E402
from core.robots import Robots, RobotsDisallowed, RobotsUnknown           # noqa: E402
from core import sync as syncm                        # noqa: E402
from core.util import parse_date                      # noqa: E402

log = logging.getLogger("jobfinder")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", type=Path, default=ROOT / "profile.md")
    ap.add_argument("--registry", type=Path, default=ROOT / "registry" / "sources.csv")
    ap.add_argument("--db", type=Path, default=ROOT / "jobfinder.db")
    ap.add_argument("--out", type=Path, default=ROOT / "out")
    ap.add_argument("--scorer", choices=["keyword", "api"], default=None, help="default from config (keyword)")
    ap.add_argument("--confirm-api", action="store_true", help="skip the interactive YES for the API scorer")
    ap.add_argument("--no-sync", action="store_true", help="do not git add/commit/push")
    ap.add_argument("--no-fetch", action="store_true", help="skip stage 1/2, re-score and re-render only")
    ap.add_argument("--only", help="comma-separated source ids to fetch")
    ap.add_argument("--rescore", action="store_true", help="re-score every open posting, not only new ones")
    ap.add_argument("--today", type=parse_date, default=date.today(), help="override the run date (tests)")
    return ap.parse_args(argv)


def keyword_hit(p: dict, keywords: list[str]) -> bool:
    blob = f"{p.get('title','')} {p.get('body_text','')[:1500]}".lower()
    return any(k.lower() in blob for k in keywords)


def main(argv=None) -> int:
    a = parse_args(argv)
    cfg = load_config(ROOT)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])
    (ROOT / "logs").mkdir(exist_ok=True)
    a.out.mkdir(parents=True, exist_ok=True)
    today = a.today

    try:
        profile = load_profile(a.profile)
    except ProfileMissing as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if profile.missing():
        print("ERROR: profile.md lacks sections: " + ", ".join(profile.missing()), file=sys.stderr)
        return 2
    os.environ["JOBFINDER_PROFILE"] = str(a.profile)

    con = dbm.connect(a.db)
    n_rows, problems = load_into_db(con, a.registry)
    log.info("registry: %d rows loaded, %d with problems", n_rows, len(problems))
    for sid, prob in problems:
        log.warning("registry row %s: %s", sid, prob)

    run_id = dbm.start_run(con)
    never = {r["url"].split("/")[2] for r in con.execute(
        "SELECT url FROM sources WHERE robots_allows='never' AND url LIKE 'http%'")}
    fetcher = Fetcher(cfg, con, run_id, blocked_hosts=never, log_path=ROOT / "logs" / "fetch.log")
    fetcher.robots = Robots(con, fetcher, ua_token="jobfinder")

    errors, ok, failed, new_ids = [], 0, 0, []
    manual_sources = []
    sources = con.execute("SELECT * FROM sources ORDER BY id").fetchall()
    only = set(a.only.split(",")) if a.only else None

    # ---- stage 1: listings ------------------------------------------------------------------
    for s in sources:
        s = dict(s)
        if not s["active"]:
            continue
        if s["platform"] == "manual" or s["robots_allows"] == "never":
            manual_sources.append(s)
            continue
        if a.no_fetch or (only and s["id"] not in only):
            continue
        try:
            adapter = get_adapter(s["platform"])
            postings = adapter.list_postings(s, fetcher, cfg)
        except NotImplementedError as e:
            log.info("source %s: %s -> shown as manual link", s["id"], e)
            manual_sources.append({**s, "block_reason": f"adapter pending: {e}"})
            continue
        except RobotsDisallowed as e:
            log.warning("source %s: %s -> manual_check", s["id"], e)
            con.execute("UPDATE sources SET robots_allows='no', last_checked=? WHERE id=?", (today.isoformat(), s["id"]))
            manual_sources.append({**s, "block_reason": f"robots.txt disallows: {e}"})
            failed += 1
            errors.append({"source": s["id"], "error": f"robots: {e}"})
            continue
        except (RobotsUnknown, BlockedHost) as e:
            log.warning("source %s: %s", s["id"], e)
            errors.append({"source": s["id"], "error": str(e)})
            failed += 1
            continue
        except Exception as e:                     # adapters never crash the run
            log.error("source %s failed: %s", s["id"], e)
            errors.append({"source": s["id"], "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-800:]})
            failed += 1
            continue
        ok += 1
        con.execute("UPDATE sources SET robots_allows='yes', last_checked=? WHERE id=?", (today.isoformat(), s["id"]))
        seen = []
        for p in postings:
            pid, is_new = dbm.upsert_posting(con, s["id"], p, today)
            seen.append(p.external_id)
            if is_new:
                new_ids.append(pid)
                dbm.detect_reposts(con, pid)
        gone = dbm.mark_gone(con, s["id"], seen, today)
        log.info("source %s: %d listed, %d new, %d gone", s["id"], len(postings), sum(1 for p in postings), gone)
        con.commit()
    expired = dbm.expire_by_deadline(con, today)
    con.commit()

    # ---- gates + pre-filter, then stage 2 for survivors --------------------------------------
    to_score = con.execute(
        "SELECT p.*, s.platform, s.name AS source_name FROM postings p JOIN sources s ON s.id=p.source_id "
        "WHERE p.status='open' AND (? OR p.id NOT IN (SELECT posting_id FROM verdicts))",
        (1 if a.rescore else 0,)).fetchall()
    stage2_budget = cfg.stage2_max
    scorer_mode = a.scorer or cfg.scorer_mode
    scored, survivors = 0, []
    for row in to_score:
        p = dict(row)
        gates = run_gates(p, profile, cfg)
        if any(g.status == "FAIL" for g in gates):
            dbm.save_verdict(con, p["id"], "NO-GO", [f"{g.name}: {g.reason}" for g in gates if g.status == "FAIL"],
                             [], [{"gates": [g.__dict__ for g in gates]}], "gates")
            scored += 1
            continue
        if not keyword_hit(p, cfg.keywords):
            dbm.save_verdict(con, p["id"], "NO-GO", [], [], [{"prefilter": "no scope keyword in title/teaser",
                                                                "gates": [g.__dict__ for g in gates]}], "prefilter")
            scored += 1
            continue
        if not a.no_fetch and stage2_budget > 0 and not p.get("detail_fetched") and p.get("url"):
            try:
                adapter = get_adapter(p["platform"])
                fd = getattr(adapter, "fetch_detail", None)
                if fd:
                    text = fd(p, fetcher, cfg)
                    if text:
                        p["body_text"] = text
                        con.execute("UPDATE postings SET body_text=?, detail_fetched=1 WHERE id=?", (text, p["id"]))
                        dl_fn = getattr(adapter, "deadline_from_detail", None)
                        if dl_fn and not p.get("deadline"):
                            dl = dl_fn(text)
                            if dl:
                                p["deadline"] = dl.isoformat()
                                con.execute("UPDATE postings SET deadline=? WHERE id=?", (dl.isoformat(), p["id"]))
                    stage2_budget -= 1
            except (RobotsDisallowed, RobotsUnknown, BlockedHost) as e:
                log.warning("stage 2 skipped for posting %s: %s", p["id"], e)
            except Exception as e:
                log.error("stage 2 failed for posting %s: %s", p["id"], e)
                errors.append({"posting": p["id"], "error": f"{type(e).__name__}: {e}"})
        gates = run_gates(p, profile, cfg)          # re-run on full text
        if any(g.status == "FAIL" for g in gates):
            dbm.save_verdict(con, p["id"], "NO-GO", [f"{g.name}: {g.reason}" for g in gates if g.status == "FAIL"],
                             [], [{"gates": [g.__dict__ for g in gates]}], "gates")
            scored += 1
            continue
        survivors.append((p, gates))
    con.commit()

    # ---- scoring -----------------------------------------------------------------------------
    scorer_fn, scorer_name = score_keyword, "keyword"
    if scorer_mode == "api" and survivors:
        from core.scorer_api import confirm, estimate, score_api
        n = min(estimate(len(survivors)), cfg.api_max_calls)
        if not confirm(n, cfg.api_model, assume_yes=a.confirm_api):
            print("[api scorer] not confirmed - falling back to the keyword scorer")
        else:
            scorer_fn, scorer_name = score_api, f"api:{cfg.api_model}"
            survivors = survivors[:n]
    for p, gates in survivors:
        try:
            res = scorer_fn(p, profile, gates, cfg)
        except Exception as e:
            log.error("scorer failed for posting %s: %s -> keyword fallback", p["id"], e)
            errors.append({"posting": p["id"], "error": f"scorer: {e}"})
            res = score_keyword(p, profile, gates, cfg)
        dbm.save_verdict(con, p["id"], res.verdict, [], res.absent,
                         [{"reason": res.reason, "gates": [g.__dict__ for g in gates],
                           "requirements": res.evidence_rows(), "absent_desirable": res.absent_desirable}], scorer_name)
        scored += 1
    con.commit()

    # ---- render ------------------------------------------------------------------------------
    rows = []
    repost_ids = {r[0] for r in con.execute("SELECT repeat_posting_id FROM reposts")}
    for r in con.execute("SELECT p.*, v.verdict, v.absent_json, v.evidence_json, v.gates_failed, s.name AS source_name, "
                         "s.platform FROM postings p LEFT JOIN verdicts v ON v.posting_id=p.id "
                         "JOIN sources s ON s.id=p.source_id WHERE s.active=1"):
        d = dict(r)
        ev = json.loads(d.get("evidence_json") or "[]")
        ev0 = ev[0] if ev else {}
        gates = ev0.get("gates", [])
        rows.append({
            "id": d["id"], "title": d["title"], "institution": d["institution"], "country": d.get("country") or "",
            "location": d.get("location") or "",
            "url": d["url"], "status": d["status"], "verdict": d.get("verdict") or "UNSCORED",
            "deadline": parse_date(d["deadline"]) if d["deadline"] else None,
            "posted_ord": parse_date(d["posted_date"]).toordinal() if d.get("posted_date") and parse_date(d["posted_date"]) else 0,
            "absent": json.loads(d.get("absent_json") or "[]"), "reason": ev0.get("reason") or (
                "; ".join(json.loads(d.get("gates_failed") or "[]")) or ev0.get("prefilter") or ""),
            "evidence": ev0.get("requirements", []), "gates": gates,
            "gates_unknown": [g["name"] for g in gates if g.get("status") == "UNKNOWN"],
            "repost": d["id"] in repost_ids, "manual": d["platform"] == "manual", "is_new": d["id"] in set(new_ids),
            "source_name": d["source_name"],
        })
    from core.gates import guess_country
    for r in rows:                                   # fall back to the gates' country guess
        if not r["country"] or len(r["country"]) != 2:
            r["country"] = guess_country({"country": "", "title": r["title"], "institution": r["institution"],
                                          "location": r.get("location") or ""}) or r["country"]
    n_open = sum(1 for r in rows if r["status"] == "open" and r["verdict"] in ("GO", "STRETCH"))
    n_exp = sum(1 for r in rows if r["status"] != "open")
    render_queue(rows, manual_sources, today, a.out / "queue.md")
    render_positions(rows, manual_sources, today, a.out / "positions.md")
    render_dashboard(rows, manual_sources, today, a.out / "dashboard.html",
                     {"run": run_id, "sources_ok": ok, "sources_failed": failed, "new": len(new_ids),
                      "scored": scored, "requests": fetcher.count, "scorer": scorer_name})
    dbm.finish_run(con, run_id, ok, failed, len(new_ids), errors)
    write_back(con, a.registry)
    con.close()
    print(f"run {today}: {len(new_ids)} new, {n_open} open, {n_exp} expired | sources ok={ok} failed={failed} "
          f"requests={fetcher.count} scored={scored}")

    # ---- verify (banned strings) then sync (staged-key check runs on staged files) -----------
    env = {**os.environ, "JOBFINDER_PROFILE": str(a.profile)}
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", str(ROOT / "tools" / "verify_output.py"),
                        "-k", "banned"], cwd=ROOT, env=env)
    if r.returncode != 0:
        print("VERIFY FAILED: banned string in output. Not committing.", file=sys.stderr)
        return 1
    if a.no_sync or not cfg.sync_enabled:
        return 0
    try:
        syncm.stage(ROOT)
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", str(ROOT / "tools" / "verify_output.py")],
                           cwd=ROOT, env=env)
        if r.returncode != 0:
            syncm.unstage(ROOT)
            print("VERIFY FAILED on staged files. Commit aborted.", file=sys.stderr)
            return 1
        msg = f"run {today}: {len(new_ids)} new, {n_open} open, {n_exp} expired"
        print("sync:", syncm.commit_and_push(ROOT, msg, cfg.sync_remote, cfg.sync_branch))
    except Exception as e:
        log.error("sync failed (data is kept locally): %s", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
