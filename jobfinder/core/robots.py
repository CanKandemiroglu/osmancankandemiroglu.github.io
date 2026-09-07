"""robots.txt per host: fetched once per run, cached in the DB for 7 days, always respected.

Decision rule:
  * robots.txt 2xx  -> parse; allowed iff RobotFileParser says so for our UA
  * 404/410/401/403 -> treated as 'no robots.txt' -> allowed (RFC 9309 s.2.3.1.3)
  * 5xx / network   -> UNKNOWN -> we do NOT fetch this run (conservative)
  * registry says robots_allows='never' -> host is never contacted, whatever robots.txt says
"""
from __future__ import annotations
import time
import urllib.robotparser
from datetime import datetime, timedelta
from urllib.parse import urlsplit

TTL = timedelta(days=7)


class RobotsDisallowed(Exception):
    pass


class RobotsUnknown(Exception):
    pass


class Robots:
    def __init__(self, con, fetcher, ua_token: str = "jobfinder"):
        self.con = con
        self.fetcher = fetcher
        self.ua_token = ua_token
        self._parsers: dict[str, tuple[int, urllib.robotparser.RobotFileParser | None]] = {}

    def _load(self, host: str, scheme: str):
        if host in self._parsers:
            return self._parsers[host]
        row = self.con.execute("SELECT fetched_at, status, body FROM robots_cache WHERE host=?",
                               (host,)).fetchone()
        status, body = None, None
        if row and row["fetched_at"] and datetime.fromisoformat(row["fetched_at"]) > datetime.now() - TTL:
            status, body = row["status"], row["body"]
        else:
            res = self.fetcher.raw_get(f"{scheme}://{host}/robots.txt", purpose="robots")
            status, body = res.status, (res.text if res.status and res.status < 300 else "")
            if status is not None:
                self.con.execute("INSERT OR REPLACE INTO robots_cache(host, fetched_at, status, body) "
                                 "VALUES(?,?,?,?)", (host, datetime.now().isoformat(timespec="seconds"),
                                                     status, body))
                self.con.commit()
        parser = None
        if status and status < 300:
            parser = urllib.robotparser.RobotFileParser()
            parser.parse((body or "").splitlines())
        self._parsers[host] = (status, parser)
        return self._parsers[host]

    def check(self, url: str) -> str:
        """Returns 'yes' or raises RobotsDisallowed / RobotsUnknown."""
        u = urlsplit(url)
        status, parser = self._load(u.netloc.lower(), u.scheme or "https")
        if status is None or status >= 500:
            raise RobotsUnknown(f"robots.txt for {u.netloc} unreachable (status {status})")
        if parser is None:                       # 4xx -> no robots.txt
            return "yes"
        path = u.path or "/"
        if u.query:
            path += "?" + u.query
        for agent in (self.ua_token, "*"):
            if not parser.can_fetch(agent, path):
                raise RobotsDisallowed(f"{u.netloc} robots.txt disallows {path} for {agent!r}")
        delay = parser.crawl_delay(self.ua_token) or parser.crawl_delay("*")
        if delay:
            self.fetcher.set_host_delay(u.netloc.lower(), float(delay))
        return "yes"
