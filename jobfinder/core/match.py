"""Gap-list matcher. Never a percentage.

For each requirement extracted verbatim from the ad:
  evidence: a profile §3a / §3b entry, or "NOT EVIDENCED"
  tier:     HIS HANDS | TAUGHT | ABSENT   (EXCLUDED when a §3c method is essential)
Verdict rules (from the spec; two cases the spec leaves open are marked *):
  GO      = every essential is HIS HANDS and no gate failed/unknown
  STRETCH = 1-2 essentials only TAUGHT, or exactly 1 essential ABSENT
            (* >=3 TAUGHT with 0 ABSENT -> STRETCH)
  NO-GO   = a gate failed, or >=3 essentials ABSENT, or a §3c method is essential
            (* exactly 2 essentials ABSENT -> NO-GO)
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

STOP = set("""a an the and or of in on for with to by from as at is are be been being have has had
experience knowledge skills skill ability strong good excellent proven demonstrated background
degree master masters msc bsc phd required requirement desirable advantage plus preferred
including etc field fields work working research scientific science candidate candidates
applicant applicants you your we our this that these those will should must can may using use
data analysis methods method techniques technique tools tool relevant related area areas
years year least minimum one two three""".split())

REQ_SECTION = re.compile(r"^(your profile|requirements?|qualifications?|we expect|what we expect|"
                         r"essential|desirable|required qualifications|preferred qualifications|"
                         r"profile|skills|candidate profile|ihr profil|voraussetzungen|anforderungen|"
                         r"requisitos|perfil|profil recherché|competences|eligibility|who we are looking for|"
                         r"what you bring|selection criteria)\b", re.I)
END_SECTION = re.compile(r"^(we offer|what we offer|our offer|benefits|how to apply|application|"
                         r"about (us|the)|contact|salary|wir bieten|bewerbung|unser angebot|"
                         r"conditions|the position|job description|duties|responsibilities|tasks)\b", re.I)
CUE = re.compile(r"\b(must|required|require|essential|mandatory|should have|need to|expected to|"
                 r"experience (in|with|of)|knowledge of|proficien|familiar(ity)? with|background in|"
                 r"degree in|competen|skills? in|ability to|expertise in|track record|erfahrung|kenntnisse|"
                 r"abgeschlossen|voraussetzung)\b", re.I)
DESIRABLE = re.compile(r"\b(desirable|an? (distinct |strong )?(advantage|asset|plus)|preferred|preferably|"
                       r"would be (an )?(advantage|beneficial|welcome)|ideally|nice to have|bonus|"
                       r"wünschenswert|von vorteil|valorado|apprécié)\b", re.I)


@dataclass
class Requirement:
    text: str
    essential: bool
    generic: bool = False
    tier: str = "ABSENT"
    evidence: str = "NOT EVIDENCED"


@dataclass
class MatchResult:
    verdict: str
    requirements: list = field(default_factory=list)
    gates: list = field(default_factory=list)
    reason: str = ""

    @property
    def absent(self) -> list[str]:
        return [r.text for r in self.requirements if r.tier == "ABSENT" and r.essential and not r.generic]

    @property
    def absent_desirable(self) -> list[str]:
        return [r.text for r in self.requirements if r.tier == "ABSENT" and (not r.essential or r.generic)]

    def evidence_rows(self) -> list[dict]:
        return [{"requirement": r.text, "essential": r.essential, "generic": r.generic,
                 "tier": r.tier, "evidence": r.evidence} for r in self.requirements]


def split_units(text: str) -> list[str]:
    units = []
    for line in text.splitlines():
        line = line.strip(" \t-•*·")
        if not line:
            continue
        for s in re.split(r"(?<=[.;])\s+(?=[A-ZÄÖÜ])", line):
            s = s.strip()
            if 15 <= len(s) <= 400:
                units.append(s)
    return units


def extract_requirements(text: str, generic_patterns: list[str]) -> list[Requirement]:
    out, seen = [], set()
    in_req = False
    for line in text.splitlines():
        stripped = line.strip(" \t-•*·:")
        if not stripped:
            continue
        if REQ_SECTION.match(stripped) and len(stripped) < 60:
            in_req = True
            continue
        if END_SECTION.match(stripped) and len(stripped) < 60:
            in_req = False
            continue
        for unit in split_units(stripped):
            if unit.lower() in seen:
                continue
            if in_req or CUE.search(unit):
                seen.add(unit.lower())
                low = unit.lower()
                out.append(Requirement(text=unit, essential=not DESIRABLE.search(unit),
                                       generic=any(g.lower() in low for g in generic_patterns)))
    return out[:60]


def _terms(entry: str) -> tuple[str, set[str]]:
    core = re.sub(r"\(.*?\)", " ", entry)            # drop parentheticals for the phrase
    phrase = re.sub(r"[^a-z0-9+\- ]", " ", core.lower()).strip()
    toks = {t for t in re.split(r"[\s/,;]+", re.sub(r"[^a-z0-9+\-]", " ", entry.lower()))
            if len(t) >= 4 and t not in STOP}
    return phrase, toks


def _stem(t: str) -> str:
    return re.sub(r"(ies|es|s|ing|ed|ic|al|ical|y)$", "", t) if len(t) > 5 else t


def _hits(req: str, entry: str) -> bool:
    phrase, toks = _terms(entry)
    low = req.lower()
    if phrase and len(phrase) >= 5 and phrase in low:
        return True
    rtoks = {_stem(t) for t in re.findall(r"[a-z0-9+\-]{4,}", low)}
    etoks = {_stem(t) for t in toks}
    common = rtoks & etoks
    if not etoks:
        return False
    if len(etoks) == 1:
        return bool(common)
    return len(common) >= 2 or (len(common) == 1 and len(next(iter(common))) >= 8)


def classify(req: Requirement, profile) -> Requirement:
    for e in profile.hands:
        if _hits(req.text, e):
            req.tier, req.evidence = "HIS HANDS", f"§3a: {e}"
            return req
    for e in profile.taught:
        if _hits(req.text, e):
            req.tier, req.evidence = "TAUGHT", f"§3b: {e}"
            return req
    for e in profile.excluded:
        if _hits(req.text, e):
            req.tier, req.evidence = "EXCLUDED", f"§3c: {e}"
            return req
    req.tier, req.evidence = "ABSENT", "NOT EVIDENCED"
    return req


def decide(reqs: list[Requirement], gates: list) -> tuple[str, str]:
    failed = [g for g in gates if g.status == "FAIL"]
    if failed:
        return "NO-GO", "gate failed: " + "; ".join(f"{g.name}: {g.reason}" for g in failed)
    ess = [r for r in reqs if r.essential and not r.generic]
    if not ess:
        return "STRETCH", "no requirement sentences found in ad text - read it yourself"
    if any(r.tier == "EXCLUDED" for r in ess):
        return "NO-GO", "a §3c (excluded) method is essential"
    absent = sum(1 for r in ess if r.tier == "ABSENT")
    taught = sum(1 for r in ess if r.tier == "TAUGHT")
    unknown = [g for g in gates if g.status == "UNKNOWN"]
    if absent >= 2:
        return "NO-GO", f"{absent} essential requirements ABSENT"
    if absent == 1:
        return "STRETCH", "1 essential ABSENT (learnable in post?)"
    if taught >= 1:
        return "STRETCH", f"{taught} essential(s) only TAUGHT"
    if unknown:
        return "STRETCH", "all essentials evidenced but gate UNKNOWN: " + "; ".join(g.reason for g in unknown)
    return "GO", "all essentials in own hands"


def score_keyword(posting: dict, profile, gates: list, cfg) -> MatchResult:
    text = posting.get("body_text") or ""
    reqs = [classify(r, profile) for r in extract_requirements(text, cfg.generic_requirements)]
    verdict, reason = decide(reqs, gates)
    return MatchResult(verdict=verdict, requirements=reqs, gates=gates, reason=reason)
