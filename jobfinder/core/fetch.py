"""Rate-limited, robots-respecting, logged HTTP fetcher. Failures never raise past FetchResult
except for policy errors (RobotsDisallowed / RobotsUnknown / BlockedHost)."""
from __future__ import annotations
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import requests

log = logging.getLogger("jobfinder.fetch")


class BlockedHost(Exception):
    """Host is on the registry's never-fetch list (robots_allows='never')."""


@dataclass
class FetchResult:
    url: str
    status: Optional[int]
    content: bytes
    elapsed_ms: int
    error: Optional[str] = None
    final_url: str = ""
    encoding: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300 and not self.error

    @property
    def text(self) -> str:
        if not self.content:
            return ""
        enc = self.encoding or "utf-8"
        try:
            return self.content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            return self.content.decode("utf-8", errors="replace")


class Fetcher:
    def __init__(self, config, con=None, run_id: Optional[int] = None,
                 blocked_hosts: Optional[set] = None, log_path: Optional[Path] = None):
        self.config = config
        self.con = con
        self.run_id = run_id
        self.blocked_hosts = {h.lower() for h in (blocked_hosts or set())}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.user_agent
        self.session.headers["Accept-Language"] = "en, de;q=0.8, fr;q=0.6, es;q=0.6, it;q=0.6"
        if config.ca_bundle:
            self.session.verify = config.ca_bundle
        self._last: dict[str, float] = {}
        self._delay: dict[str, float] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._glock = threading.Lock()
        self.robots = None           # set by run.py after construction
        self.count = 0
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_path, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            log.addHandler(fh)
            log.setLevel(logging.INFO)

    def set_host_delay(self, host: str, seconds: float) -> None:
        self._delay[host] = max(self.config.min_delay_s, seconds)

    def _host_lock(self, host: str) -> threading.Lock:
        with self._glock:
            return self._locks.setdefault(host, threading.Lock())

    def _is_blocked(self, host: str) -> bool:
        host = host.lower()
        return any(host == b or host.endswith("." + b) for b in self.blocked_hosts)

    def raw_get(self, url: str, purpose: str = "page", method: str = "GET", **kw) -> FetchResult:
        """One request, rate-limited per host, logged. Does NOT consult robots.txt (robots.txt
        itself is fetched through here). Refuses never-fetch hosts."""
        host = urlsplit(url).netloc.lower()
        if self._is_blocked(host):
            raise BlockedHost(f"{host} is on the never-fetch list")
        lock = self._host_lock(host)
        with lock:                                   # 1 concurrent request per host
            wait = self._delay.get(host, self.config.min_delay_s) - (time.monotonic() - self._last.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            t0 = time.monotonic()
            status, content, err, final, enc = None, b"", None, url, None
            try:
                r = self.session.request(method, url, timeout=self.config.timeout_s, **kw)
                status, content, final, enc = r.status_code, r.content, r.url, r.encoding
                if r.apparent_encoding and (not enc or enc.lower() == "iso-8859-1"):
                    enc = r.apparent_encoding
            except requests.RequestException as e:
                err = f"{type(e).__name__}: {str(e)[:200]}"
            self._last[host] = time.monotonic()
        elapsed = int((time.monotonic() - t0) * 1000)
        self.count += 1
        log.info("%s %s host=%s status=%s bytes=%d elapsed=%dms%s", purpose, method, host, status,
                 len(content), elapsed, f" error={err}" if err else "")
        if self.con is not None:
            from core.db import log_fetch
            log_fetch(self.con, self.run_id, host, url, status, len(content), elapsed, err)
        return FetchResult(url, status, content, elapsed, err, final, enc)

    def get(self, url: str, **kw) -> FetchResult:
        """Policy-checked fetch: never-fetch list, then robots.txt, then the request."""
        if self.robots is not None:
            self.robots.check(url)
        return self.raw_get(url, **kw)

    def post(self, url: str, **kw) -> FetchResult:
        if self.robots is not None:
            self.robots.check(url)
        return self.raw_get(url, method="POST", **kw)
