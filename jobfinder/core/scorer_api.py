"""Anthropic API scorer. DEFAULT OFF. One ad per call, structured JSON out.
It never runs without an explicit confirmation of the estimated call count.
The key is read from the environment (ANTHROPIC_API_KEY, populated from .env) and never logged."""
from __future__ import annotations
import json
import os
import re
from core.match import MatchResult, Requirement, decide

SYSTEM = """You compare ONE job advertisement against a candidate profile.
Extract every requirement VERBATIM from the ad. For each, state whether the profile lists it under
section 3a (HIS HANDS), 3b (TAUGHT), 3c (EXCLUDED), or not at all (ABSENT). Quote the profile entry
as evidence or write "NOT EVIDENCED". Never infer a skill from an adjacent one. Never invent facts.
Mark a requirement essential=false only if the ad itself calls it desirable/advantage/preferred.
Mark generic=true for soft requirements (language, teamwork, motivation).
Return ONLY JSON: {"requirements":[{"text":..., "essential":true, "generic":false,
"tier":"HIS HANDS|TAUGHT|EXCLUDED|ABSENT", "evidence":...}]}"""


def estimate(n_postings: int) -> int:
    return n_postings


def confirm(n_calls: int, model: str, assume_yes: bool = False) -> bool:
    print(f"[api scorer] {n_calls} API call(s) to {model} would be made. This costs money.")
    if assume_yes:
        print("[api scorer] confirmed via --confirm-api")
        return True
    try:
        ans = input("[api scorer] proceed? type YES to continue: ")
    except EOFError:
        ans = ""
    return ans.strip() == "YES"


def score_api(posting: dict, profile, gates: list, cfg) -> MatchResult:
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("pip install anthropic to use the API scorer") from e
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set (put it in .env)")
    client = anthropic.Anthropic()
    prof = "\n".join(
        [f"## 3a HIS HANDS\n" + "\n".join(f"- {x}" for x in profile.hands),
         f"## 3b TAUGHT\n" + "\n".join(f"- {x}" for x in profile.taught),
         f"## 3c EXCLUDED\n" + "\n".join(f"- {x}" for x in profile.excluded)])
    ad = f"TITLE: {posting.get('title')}\nINSTITUTION: {posting.get('institution')}\n\n{(posting.get('body_text') or '')[:12000]}"
    msg = client.messages.create(
        model=cfg.api_model, max_tokens=2000, system=SYSTEM,
        messages=[{"role": "user", "content": f"PROFILE:\n{prof}\n\nADVERTISEMENT:\n{ad}"}])
    raw = "".join(getattr(b, "text", "") for b in msg.content)
    m = re.search(r"\{.*\}", raw, re.S)
    data = json.loads(m.group(0)) if m else {"requirements": []}
    reqs = []
    for r in data.get("requirements", []):
        tier = r.get("tier", "ABSENT")
        if tier not in ("HIS HANDS", "TAUGHT", "EXCLUDED", "ABSENT"):
            tier = "ABSENT"
        reqs.append(Requirement(text=str(r.get("text", ""))[:400], essential=bool(r.get("essential", True)),
                                generic=bool(r.get("generic", False)), tier=tier,
                                evidence=str(r.get("evidence") or "NOT EVIDENCED")[:300]))
    verdict, reason = decide(reqs, gates)
    return MatchResult(verdict=verdict, requirements=reqs, gates=gates, reason=reason)
