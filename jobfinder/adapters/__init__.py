"""Adapter registry: platform name (registry/sources.csv column `platform`) -> module.

Every module exposes  list_postings(source, fetcher, config) -> list[Posting]
and optionally       fetch_detail(posting, fetcher, config) -> str (full ad text).
Stubs raise NotImplementedError; the run logs them and moves on.
"""
import importlib

PLATFORMS = {
    # verified against live pages on 2026-09-07 (see tests/fixtures)
    "peopleadmin": "adapters.peopleadmin",
    "unige_wdportal": "adapters.unige_wdportal",
    "euraxess": "adapters.euraxess",
    "rss": "adapters.rss",
    "kuleuven": "adapters.kuleuven",
    "csic_sede": "adapters.csic_sede",
    "wordpress": "adapters.wordpress",
    # identified by the report but structure NOT verifiable from the build sandbox
    "szn_joomla": "adapters.szn_joomla",
    # endpoints being researched separately - do not guess them
    "workday": "adapters.stubs",
    "jobbnorge": "adapters.stubs",
    "successfactors": "adapters.stubs",
    "varbi": "adapters.stubs",
    "cnrs": "adapters.stubs",
    "pageup": "adapters.stubs",
    "reachmee": "adapters.stubs",
    "oracle_hcm": "adapters.stubs",
    "uc_recruit": "adapters.stubs",
    "taleo": "adapters.stubs",
    "emply": "adapters.stubs",
    "valtiolle": "adapters.stubs",
    "starfatorg": "adapters.stubs",
    # surfaced as a link only, never parsed
    "manual": "adapters.manual",
}


def get_adapter(platform: str):
    name = (platform or "manual").strip().lower()
    modname = PLATFORMS.get(name)
    if modname is None:
        raise KeyError(f"unknown platform {platform!r}")
    return importlib.import_module(modname)
