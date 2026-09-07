"""Commit out/, registry/sources.csv and jobfinder.db; push. Never an empty commit; a failed push
never loses data (exit 0, the next run pushes both)."""
from __future__ import annotations
import logging
import subprocess
from pathlib import Path

log = logging.getLogger("jobfinder.sync")
PATHS = ["out", "registry/sources.csv", "jobfinder.db"]


def _git(repo: Path, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=check)


def repo_root(start: Path) -> Path:
    return Path(_git(start, "rev-parse", "--show-toplevel").stdout.strip())


def stage(app_root: Path) -> list[str]:
    repo = repo_root(app_root)
    rel = app_root.relative_to(repo)
    paths = [str(rel / p) for p in PATHS if (app_root / p).exists()]
    _git(repo, "add", "--", *paths)
    return _git(repo, "diff", "--cached", "--name-only").stdout.split()


def unstage(app_root: Path) -> None:
    _git(repo_root(app_root), "reset", "-q", check=False)


def commit_and_push(app_root: Path, message: str, remote: str, branch: str) -> str:
    repo = repo_root(app_root)
    if not _git(repo, "diff", "--cached", "--name-only").stdout.strip():
        log.info("sync: nothing changed, no commit")
        return "unchanged"
    _git(repo, "commit", "-q", "-m", message)
    log.info("sync: committed '%s'", message)
    try:
        _git(repo, "push", "-u", remote, branch)
        log.info("sync: pushed to %s %s", remote, branch)
        return "pushed"
    except subprocess.CalledProcessError as e:
        log.warning("sync: push failed (kept locally, next run pushes both): %s", (e.stderr or "")[:300])
        return "push_failed"
