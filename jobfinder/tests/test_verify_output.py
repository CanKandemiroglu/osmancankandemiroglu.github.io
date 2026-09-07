"""verify_output must catch a banned string and an API-key-looking string."""
from pathlib import Path
from tools import verify_output as vo
from conftest import FIX


def test_banned_string_is_caught(tmp_path):
    (tmp_path / "queue.md").write_text("# queue\n- title: Unicorn   Wrangler wanted\n", encoding="utf-8")
    (tmp_path / "positions.md").write_text("clean\n", encoding="utf-8")
    hits = vo.find_banned(vo.output_files(tmp_path), vo.banned_regexes(FIX / "profile_fixture.md"))
    assert hits and hits[0][1] == "unicorn wrangler"


def test_clean_output_passes(tmp_path):
    (tmp_path / "queue.md").write_text("# queue\nnothing today\n", encoding="utf-8")
    assert vo.find_banned(vo.output_files(tmp_path), vo.banned_regexes(FIX / "profile_fixture.md")) == []


def test_api_key_pattern_is_caught(tmp_path):
    f = tmp_path / "x.env"
    f.write_text("ANTHROPIC_API_KEY=sk-ant-api03-" + "A" * 40 + "\n", encoding="utf-8")
    assert vo.find_keys([f])
    g = tmp_path / "ok.md"
    g.write_text("no secrets here\n", encoding="utf-8")
    assert vo.find_keys([g]) == []
