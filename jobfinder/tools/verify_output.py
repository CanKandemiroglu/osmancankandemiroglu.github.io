"""Guardrail test. Run by run.py at the end of every run; a hit FAILS the run.

  1. No banned string from profile.md §7 appears in out/queue.md, out/positions.md,
     out/dashboard.html or any *summary* file under out/. Regexes are built from §7 at runtime.
  2. No file staged for commit contains something that looks like an API key.

Usage:  pytest tools/verify_output.py  [--profile PATH]   or   python tools/verify_output.py
"""
from __future__ import annotations
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

KEY_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"),
    re.compile(r"(?i)\b(api[_\-]?key|secret|token)\b\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{24,}"),
]


def profile_path() -> Path:
    return Path(os.environ.get("JOBFINDER_PROFILE") or ROOT / "profile.md")


def banned_regexes(path: Path | None = None) -> list[tuple[str, re.Pattern]]:
    from core.profile import load_profile
    prof = load_profile(path or profile_path())
    out = []
    for s in prof.banned_strings():
        pat = r"\s+".join(re.escape(w) for w in s.split())
        out.append((s, re.compile(pat, re.I)))
    return out


def output_files(out_dir: Path | None = None) -> list[Path]:
    out_dir = out_dir or ROOT / "out"
    files = [out_dir / "queue.md", out_dir / "positions.md", out_dir / "dashboard.html"]
    files += sorted(out_dir.glob("*summary*"))
    return [f for f in files if f.exists()]


def find_banned(files: list[Path], regexes) -> list[tuple[str, str, str]]:
    hits = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        for s, rx in regexes:
            m = rx.search(text)
            if m:
                i = max(0, m.start() - 40)
                hits.append((f.name, s, text[i:m.end() + 40].replace("\n", " ")))
    return hits


def staged_files() -> list[Path]:
    try:
        top = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
        names = subprocess.run(["git", "-C", top, "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                               capture_output=True, text=True, check=True).stdout.split()
        return [Path(top) / n for n in names]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def find_keys(files: list[Path]) -> list[tuple[str, str]]:
    hits = []
    for f in files:
        if not f.is_file() or f.suffix in (".db", ".sqlite", ".png", ".jpg", ".pdf"):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for rx in KEY_PATTERNS:
            m = rx.search(text)
            if m:
                hits.append((str(f), m.group(0)[:12] + "…"))
                break
    return hits


# ---- pytest entry points -------------------------------------------------------------------

def test_no_banned_strings_in_outputs():
    regexes = banned_regexes()
    assert regexes, "profile.md §7 has no banned strings - the guardrail would be vacuous"
    hits = find_banned(output_files(), regexes)
    assert not hits, "banned string(s) in output: " + "; ".join(f"{f}: {s!r} …{ctx}…" for f, s, ctx in hits)


def test_no_api_keys_staged():
    hits = find_keys(staged_files())
    assert not hits, "possible API key in staged file(s): " + "; ".join(f"{f} ({k})" for f, k in hits)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main(["-q", __file__]))
