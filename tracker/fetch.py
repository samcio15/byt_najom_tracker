"""Polite HTTP client: one session, random delays, retries, debug dumps."""
from __future__ import annotations

import logging
import random
import time
from pathlib import Path

import requests

from . import config

log = logging.getLogger(__name__)
DEBUG_DIR = Path("data/debug")


class Fetcher:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "sk-SK,sk;q=0.9,cs;q=0.8,en;q=0.6",
        })
        self._last = 0.0

    def get(self, url: str, params: dict | None = None) -> str | None:
        wait = random.uniform(*config.REQUEST_DELAY) - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        for attempt in range(3):
            try:
                r = self.s.get(url, params=params, timeout=config.TIMEOUT)
                self._last = time.time()
                if r.status_code == 200:
                    r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
                    return r.text
                if r.status_code == 404:
                    return None
                log.warning("HTTP %s for %s (attempt %d)", r.status_code, r.url, attempt + 1)
            except requests.RequestException as e:
                log.warning("Request error %s for %s (attempt %d)", e, url, attempt + 1)
            time.sleep(5 * (attempt + 1))
        return None


def dump_debug(name: str, html: str) -> None:
    """Save a page that failed to parse, so the parser can be fixed."""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    (DEBUG_DIR / name).write_text(html or "", encoding="utf-8")
    log.warning("Saved unparseable page to %s", DEBUG_DIR / name)
