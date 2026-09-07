"""Configuration: defaults <- jobfinder.toml <- environment (.env is read into the env)."""
from __future__ import annotations
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_KEYWORDS = [
    "marine", "ocean", "sea ", "biogeochem", "geochem", "sediment", "microbi",
    "phytoplankton", "lipid", "biomarker", "isotope", "coastal", "estuar", "aquatic",
    "benthic", "pelagic", "polar", "arctic", "antarctic", "carbon", "mass spectrom",
    "organic matter", "astrobiolog", "limnolog", "paleo", "palaeo", "meer", "ozean", "meeres", "marin", "océan", "oceano", "geoq", "biogeoq", "mare ",
]
DEFAULT_GENERIC = [
    "english", "communication", "team", "motivat", "independen", "willing",
    "driving licen", "german language", "language skills", "interpersonal",
    "presentation skills", "writing skills", "fieldwork at sea", "sea-going", "seagoing", "cruise",
]


@dataclass
class Config:
    contact_email: str = "osmancankandemiroglu@proton.me"
    min_delay_s: float = 2.0
    timeout_s: float = 30.0
    max_pages: int = 5
    stage2_max: int = 40
    wisszeitvg_remaining_months: Optional[int] = None
    keywords: list = field(default_factory=lambda: list(DEFAULT_KEYWORDS))
    generic_requirements: list = field(default_factory=lambda: list(DEFAULT_GENERIC))
    scorer_mode: str = "keyword"
    api_model: str = "claude-sonnet-5"
    api_max_calls: int = 30
    sync_enabled: bool = True
    sync_remote: str = "origin"
    sync_branch: str = "main"
    ca_bundle: Optional[str] = None
    root: Path = ROOT

    @property
    def user_agent(self) -> str:
        return f"jobfinder/0.1 (personal PhD-position monitor; contact: {self.contact_email})"


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader. Values never leave os.environ."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def load_config(root: Path = ROOT) -> Config:
    cfg = Config(root=root)
    _load_dotenv(root / ".env")
    toml_path = root / "jobfinder.toml"
    if toml_path.exists():
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        for k in ("contact_email", "min_delay_s", "timeout_s", "max_pages", "stage2_max",
                  "wisszeitvg_remaining_months", "keywords", "generic_requirements"):
            if k in data:
                setattr(cfg, k, data[k])
        sc = data.get("scorer", {})
        cfg.scorer_mode = sc.get("mode", cfg.scorer_mode)
        cfg.api_model = sc.get("api_model", cfg.api_model)
        cfg.api_max_calls = int(sc.get("api_max_calls", cfg.api_max_calls))
        sy = data.get("sync", {})
        cfg.sync_enabled = bool(sy.get("enabled", cfg.sync_enabled))
        cfg.sync_remote = sy.get("remote", cfg.sync_remote)
        cfg.sync_branch = sy.get("branch", cfg.sync_branch)
    env = os.environ
    if env.get("JOBFINDER_CONTACT_EMAIL"):
        cfg.contact_email = env["JOBFINDER_CONTACT_EMAIL"]
    if env.get("JOBFINDER_WISSZEITVG_MONTHS"):
        cfg.wisszeitvg_remaining_months = int(env["JOBFINDER_WISSZEITVG_MONTHS"])
    cfg.ca_bundle = env.get("JOBFINDER_CA_BUNDLE") or env.get("REQUESTS_CA_BUNDLE") or None
    return cfg
