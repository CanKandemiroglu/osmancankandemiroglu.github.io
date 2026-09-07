"""profile.md is the ONLY source of facts about the candidate. This module only reads it.

Expected layout (headings may carry any wording; the section id is the leading token):
  ## 3a ...   methods/skills in the candidate's own hands      -> tier HIS HANDS
  ## 3b ...   methods taught / course-level                    -> tier TAUGHT
  ## 3c ...   methods explicitly excluded                      -> NO-GO when essential
  ## 4  ...   eligibility facts as `- key: value` bullets:
                highest_degree: MSc
                work_authorization: EU/EEA           (regions where no visa is needed)
                wisszeitvg_remaining_months: 0       (optional; jobfinder.toml/env may set it)
  ## 7  ...   banned strings, one per bullet (quotes/backticks optional)
Anything missing is reported as missing, never filled in.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})\s*(?:§\s*)?(\d+[a-z]?)\b[.:)\s-]*(.*)$", re.I)
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")


class ProfileMissing(FileNotFoundError):
    pass


@dataclass
class Section:
    sid: str
    title: str
    lines: list = field(default_factory=list)

    @property
    def items(self) -> list[str]:
        out = []
        for ln in self.lines:
            m = BULLET.match(ln)
            if m and m.group(1).strip():
                out.append(m.group(1).strip())
        return out

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def kv(self) -> dict[str, str]:
        d = {}
        for it in self.items:
            if ":" in it:
                k, v = it.split(":", 1)
                d[re.sub(r"[^a-z0-9_]", "_", k.strip().lower().strip("*`_"))] = v.strip().strip("*`")
        return d


@dataclass
class Profile:
    path: Path
    sections: dict[str, Section]

    def sec(self, sid: str) -> Section | None:
        return self.sections.get(sid.lower())

    def items(self, sid: str) -> list[str]:
        s = self.sec(sid)
        return s.items if s else []

    @property
    def hands(self) -> list[str]:
        return self.items("3a")

    @property
    def taught(self) -> list[str]:
        return self.items("3b")

    @property
    def excluded(self) -> list[str]:
        return self.items("3c")

    def gates_config(self) -> dict[str, str]:
        s = self.sec("4")
        return s.kv() if s else {}

    def banned_strings(self) -> list[str]:
        out = []
        for it in self.items("7"):
            it = it.strip()
            m = re.match(r'^[`"\'“„](.+?)[`"\'”“]\s*(?:[-–—:].*)?$', it)
            out.append(m.group(1) if m else it)
        return [x for x in out if x]

    def missing(self) -> list[str]:
        need = {"3a": "skills in own hands", "3b": "taught skills", "3c": "excluded methods",
                "4": "eligibility gates", "7": "banned strings"}
        return [f"§{k} ({v})" for k, v in need.items() if k not in self.sections]


def load_profile(path: Path) -> Profile:
    if not path.exists():
        raise ProfileMissing(f"{path} not found. profile.md is required and is never generated.")
    sections: dict[str, Section] = {}
    cur = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = HEADING.match(raw.strip())
        if m:
            sid = m.group(2).lower()
            cur = Section(sid, m.group(3).strip())
            sections[sid] = cur
            continue
        if cur is not None:
            cur.lines.append(raw)
    return Profile(path, sections)
