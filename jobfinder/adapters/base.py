from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Posting:
    external_id: str
    title: str
    institution: str = ""
    location: str = ""
    url: str = ""
    posted_date: Optional[date] = None
    deadline: Optional[date] = None
    body_text: str = ""
    country: str = ""
    extra: dict = field(default_factory=dict)


class AdapterError(Exception):
    """Raised by an adapter when the page did not look like what it expects."""
