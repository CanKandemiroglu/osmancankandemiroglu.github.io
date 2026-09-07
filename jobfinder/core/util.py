from __future__ import annotations
import hashlib
import re
from datetime import date, datetime
from typing import Optional

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
MONTHS.update({"mär": 3, "mai": 5, "okt": 10, "dez": 12,          # de
               "ene": 1, "abr": 4, "ago": 8, "dic": 12,             # es
               "fév": 2, "avr": 4, "juin": 6, "juil": 7, "aoû": 8, "déc": 12,  # fr
               "gen": 1, "mag": 5, "giu": 6, "lug": 7, "set": 9, "ott": 10})  # it

_DATE_PATTERNS = [
    (re.compile(r"(\d{4})-(\d{2})-(\d{2})"), "ymd"),
    (re.compile(r"(\d{4})(\d{2})(\d{2})$"), "ymd"),
    (re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})"), "dmy"),
    (re.compile(r"(\d{1,2})\s+([A-Za-zäéû]{3,})\.?\s+(\d{4})"), "d_mon_y"),
    (re.compile(r"([A-Za-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})"), "mon_d_y"),
]


def parse_date(s: Optional[str], dayfirst: bool = True) -> Optional[date]:
    """Best-effort date parse. Returns None rather than guessing."""
    if not s:
        return None
    s = str(s).strip()
    for rx, kind in _DATE_PATTERNS:
        m = rx.search(s)
        if not m:
            continue
        try:
            if kind == "ymd":
                return date(int(m[1]), int(m[2]), int(m[3]))
            if kind == "dmy":
                a, b, y = int(m[1]), int(m[2]), int(m[3])
                d, mo = (a, b) if dayfirst else (b, a)
                if mo > 12 and d <= 12:
                    d, mo = mo, d
                return date(y, mo, d)
            if kind == "d_mon_y":
                mo = MONTHS.get(m[2][:3].lower())
                return date(int(m[3]), mo, int(m[1])) if mo else None
            if kind == "mon_d_y":
                mo = MONTHS.get(m[1][:3].lower())
                return date(int(m[3]), mo, int(m[2])) if mo else None
        except ValueError:
            return None
    return None


def dedup_hash(title: str, institution: str) -> str:
    norm = re.sub(r"[^a-z0-9]+", " ", f"{title} {institution}".lower()).strip()
    return hashlib.sha1(norm.encode()).hexdigest()[:16]


def days_left(deadline: Optional[date], today: Optional[date] = None) -> Optional[int]:
    if deadline is None:
        return None
    return (deadline - (today or date.today())).days


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def clean_text(s: str) -> str:
    s = re.sub(r"[ \t\r\f\v]+", " ", s or "")
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()
