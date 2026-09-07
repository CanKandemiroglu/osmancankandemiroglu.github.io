"""Deadline-aware ranking. GO before STRETCH; within a verdict, earliest deadline first;
postings without a deadline sort last."""
from __future__ import annotations
from datetime import date

ORDER = {"GO": 0, "STRETCH": 1, "UNSCORED": 2, "NO-GO": 3}


def sort_key(row: dict):
    dl = row.get("deadline")
    return (ORDER.get(row.get("verdict") or "UNSCORED", 2), dl is None, dl or date.max,
            -(row.get("posted_ord") or 0), row.get("title") or "")


def rank(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=sort_key)
