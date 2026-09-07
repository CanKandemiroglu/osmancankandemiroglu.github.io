"""Three hard eligibility gates, run BEFORE any scoring. Each returns PASS / FAIL / UNKNOWN.
FAIL -> NO-GO, never reaches the matcher. UNKNOWN -> proceeds, but is flagged and can never be GO.
Facts come from profile.md §4 and config; nothing is assumed about the candidate."""
from __future__ import annotations
import re
from dataclasses import dataclass

EU_EEA_CH = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV",
    "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "IS", "LI", "NO", "CH",
}
COUNTRY_NAMES = {
    "austria": "AT", "belgium": "BE", "bulgaria": "BG", "croatia": "HR", "cyprus": "CY", "czech": "CZ",
    "denmark": "DK", "estonia": "EE", "finland": "FI", "france": "FR", "germany": "DE", "deutschland": "DE",
    "greece": "GR", "hungary": "HU", "ireland": "IE", "italy": "IT", "italia": "IT", "latvia": "LV",
    "lithuania": "LT", "luxembourg": "LU", "malta": "MT", "netherlands": "NL", "poland": "PL",
    "portugal": "PT", "romania": "RO", "slovakia": "SK", "slovenia": "SI", "spain": "ES", "españa": "ES",
    "sweden": "SE", "iceland": "IS", "norway": "NO", "switzerland": "CH", "suisse": "CH",
    "united kingdom": "GB", "uk": "GB", "united states": "US", "usa": "US", "canada": "CA",
    "australia": "AU", "new zealand": "NZ", "japan": "JP", "greenland": "GL", "faroe": "FO",
    "belgië": "BE", "belgique": "BE", "schweiz": "CH",
}
REGION_ALIASES = {"eu": EU_EEA_CH, "eea": EU_EEA_CH, "eu/eea": EU_EEA_CH, "eu_eea": EU_EEA_CH,
                  "schengen": EU_EEA_CH, "europe": EU_EEA_CH}

PHD_LEVEL = re.compile(r"\b(phd (position|student|candidate|fellow|scholarship|studentship|researcher|project)|"
                       r"doctoral (position|student|candidate|researcher|fellow)|predoctoral|pre-doctoral|"
                       r"promotionsstelle|doktorand|doctorant|contrato predoctoral|dottorato|"
                       r"ph\.?d\.? (position|student|candidate)|early stage researcher|esr\b)", re.I)
POSTDOC_LEVEL = re.compile(r"\b(post-?doc\w*|postdoctoral|post-doctoral|research fellow|senior scientist|"
                           r"assistant professor|associate professor|professor|lecturer|group leader|"
                           r"staff scientist|principal investigator|tenure)\b", re.I)
PHD_REQUIRED = re.compile(r"\b(completed|hold|holds|holding|possess|have|has|with|obtained|awarded)\s+(a\s+|an\s+)?"
                          r"(phd|ph\.d|doctorate|doctoral degree|doktortitel|promotion)|"
                          r"(phd|ph\.d|doctorate|doctoral degree)\s+(is\s+)?(required|mandatory|essential|necessary)|"
                          r"(abgeschlossene\s+promotion|promoviert)", re.I)
NO_SPONSOR = re.compile(r"(no (visa )?sponsorship|not (able to|in a position to) sponsor|unable to sponsor|"
                        r"must (already )?(have|hold|possess) (the )?(legal )?right to work|"
                        r"(must be|only) (a )?(citizen|permanent resident)|authori[sz]ed to work in the (us|u\.s\.|united states)"
                        r"( without sponsorship)?|eligible to work in \w+ without)", re.I)
SPONSOR = re.compile(r"(visa sponsorship|sponsor(ship)? (is|will be) (available|provided)|work permit (will be|is) "
                     r"(arranged|provided|supported)|international (applicants|candidates) (are )?welcome|"
                     r"relocation (support|assistance)|assist(ance)? with (the )?(visa|work permit))", re.I)
DURATION = re.compile(r"(\d+(?:[.,]\d+)?)\s*[- ]?\s*(years?|jahre?n?|months?|monate?n?|ans?\b|años?|anni)", re.I)


@dataclass
class GateResult:
    name: str
    status: str          # PASS | FAIL | UNKNOWN
    reason: str


def guess_country(posting: dict) -> str:
    for key in ("country", "location", "institution", "title"):
        v = (posting.get(key) or "").strip()
        if not v:
            continue
        if key == "country" and len(v) == 2 and v.isalpha():
            return v.upper()
        low = v.lower()
        for name, code in COUNTRY_NAMES.items():
            if re.search(rf"\b{re.escape(name)}\b", low):
                return code
    return ""


def _authorized_set(value: str) -> set[str]:
    out = set()
    for tok in re.split(r"[,;/ ]+", value.lower()):
        tok = tok.strip()
        if not tok:
            continue
        if tok in REGION_ALIASES:
            out |= REGION_ALIASES[tok]
        elif len(tok) == 2:
            out.add(tok.upper())
        elif tok in COUNTRY_NAMES:
            out.add(COUNTRY_NAMES[tok])
    return out


def gate_wisszeitvg(posting: dict, cfg, text: str) -> GateResult:
    country = guess_country(posting)
    german = country == "DE" or re.search(r"wisszeitvg|tv-?l\b|tvöd|befristet", text, re.I)
    if not german:
        return GateResult("wisszeitvg", "PASS", "not a German fixed-term academic contract")
    months = cfg.wisszeitvg_remaining_months
    if months is None:
        return GateResult("wisszeitvg", "UNKNOWN", "German position but wisszeitvg_remaining_months is unset")
    m = DURATION.search(text)
    if not m:
        return GateResult("wisszeitvg", "UNKNOWN", f"German position; contract duration not found in ad (entitlement {months} mo)")
    n = float(m.group(1).replace(",", "."))
    unit = m.group(2).lower()
    need = n * 12 if unit.startswith(("year", "jahr", "an", "añ")) else n
    if need > months:
        return GateResult("wisszeitvg", "FAIL", f"ad duration {m.group(0)} > remaining entitlement {months} months")
    return GateResult("wisszeitvg", "PASS", f"ad duration {m.group(0)} within entitlement {months} months")


def gate_visa(posting: dict, gates_cfg: dict, text: str) -> GateResult:
    auth = gates_cfg.get("work_authorization")
    if not auth:
        return GateResult("visa", "UNKNOWN", "profile §4 has no work_authorization")
    allowed = _authorized_set(auth)
    country = guess_country(posting)
    if not country:
        return GateResult("visa", "UNKNOWN", "posting country could not be determined")
    if country in allowed:
        return GateResult("visa", "PASS", f"{country} within work_authorization")
    if NO_SPONSOR.search(text):
        return GateResult("visa", "FAIL", f"{country} outside work_authorization and ad excludes sponsorship")
    if SPONSOR.search(text):
        return GateResult("visa", "PASS", f"{country} outside work_authorization but ad offers sponsorship")
    return GateResult("visa", "UNKNOWN", f"{country} outside work_authorization; ad silent on sponsorship")


def gate_phd_required(posting: dict, gates_cfg: dict, text: str) -> GateResult:
    degree = (gates_cfg.get("highest_degree") or "").lower()
    if not degree:
        return GateResult("phd_required", "UNKNOWN", "profile §4 has no highest_degree")
    if re.search(r"phd|ph\.d|doctor|dr\.", degree):
        return GateResult("phd_required", "PASS", "candidate holds a doctorate")
    title = posting.get("title") or ""
    if PHD_LEVEL.search(title) or PHD_LEVEL.search(text[:600]):
        return GateResult("phd_required", "PASS", "PhD-level opening")
    m = POSTDOC_LEVEL.search(title)
    if m:
        return GateResult("phd_required", "FAIL", f"title says '{m.group(0)}' -> PhD required")
    m = PHD_REQUIRED.search(text)
    if m:
        return GateResult("phd_required", "FAIL", f"ad requires a doctorate: '{m.group(0)}'")
    return GateResult("phd_required", "PASS", "no doctorate requirement found")


def run_gates(posting: dict, profile, cfg) -> list[GateResult]:
    text = " ".join(filter(None, [posting.get("title"), posting.get("body_text")]))
    gc = profile.gates_config() if profile else {}
    if cfg.wisszeitvg_remaining_months is None and gc.get("wisszeitvg_remaining_months", "").strip().lstrip("-").isdigit():
        cfg.wisszeitvg_remaining_months = int(gc["wisszeitvg_remaining_months"])
    return [gate_wisszeitvg(posting, cfg, text), gate_visa(posting, gc, text), gate_phd_required(posting, gc, text)]
