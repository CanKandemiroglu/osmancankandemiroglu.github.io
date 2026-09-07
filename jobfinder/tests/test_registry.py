import sqlite3
from core import db as dbm
from core.registry import read_csv, validate, load_into_db
from conftest import ROOT


def test_registry_loads_all_rows(tmp_path):
    rows = read_csv(ROOT / "registry" / "sources.csv")
    assert len(rows) >= 38
    con = dbm.connect(tmp_path / "t.db")
    n, problems = load_into_db(con, ROOT / "registry" / "sources.csv")
    assert n == len(rows)
    assert problems == []
    inactive = {r["id"]: r["block_reason"] for r in con.execute("SELECT id, block_reason FROM sources WHERE active=0")}
    assert all(v for v in inactive.values()), "inactive rows must carry a block_reason"
    never = {r["id"] for r in con.execute("SELECT id FROM sources WHERE robots_allows='never'")}
    assert never == {"unil", "ifremer"}


def test_active_row_without_url_is_rejected(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("id,name,country,category,url,platform,tenant_id,robots_allows,block_reason,active,last_checked,notes\n"
                 "x,X,DE,u,,manual,,,,1,,\n", encoding="utf-8")
    con = dbm.connect(tmp_path / "t.db")
    n, problems = load_into_db(con, p)
    assert problems == [("x", "active but no confirmed http(s) url")]
    assert con.execute("SELECT active FROM sources WHERE id='x'").fetchone()[0] == 0


def test_never_flag_survives_reload(tmp_path):
    con = dbm.connect(tmp_path / "t.db")
    load_into_db(con, ROOT / "registry" / "sources.csv")
    con.execute("UPDATE sources SET robots_allows='yes' WHERE id='unil'")   # simulate a bug
    load_into_db(con, ROOT / "registry" / "sources.csv")
    assert con.execute("SELECT robots_allows FROM sources WHERE id='unil'").fetchone()[0] == "never"
