import sys
from pathlib import Path
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "fixtures"

import pytest
from core.config import Config
from core.fetch import FetchResult


@dataclass
class FakeFetcher:
    """Serves fixture files for known URLs; records every URL asked for."""
    routes: dict
    calls: list

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def _serve(self, url, method):
        self.calls.append((method, url))
        for key, fname in self.routes.items():
            if url.startswith(key):
                data = (FIX / fname).read_bytes()
                enc = "latin-1" if "unige" in fname and "root" not in fname else "utf-8"
                return FetchResult(url, 200, data, 1, None, url, enc)
        return FetchResult(url, 404, b"", 1, None, url, "utf-8")

    def get(self, url, **kw):
        return self._serve(url, "GET")

    def post(self, url, **kw):
        return self._serve(url, "POST")


@pytest.fixture
def cfg():
    return Config(max_pages=1)


@pytest.fixture
def profile():
    from core.profile import load_profile
    return load_profile(FIX / "profile_fixture.md")
