"""Persistent history in data/state.json (committed back to the repo by CI)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

from . import config
from .textparse import norm

STATE_PATH = Path("data/state.json")


def load(path: Path = STATE_PATH) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"listings": {}, "runs": [], "notified": []}


def save(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def fingerprint(text: str) -> str | None:
    """Hash of the start of the description; survives reposts and cross-posting."""
    t = re.sub(r"[^a-z0-9]", "", norm(text))
    if len(t) < 120:
        return None
    return hashlib.sha1(t[:300].encode()).hexdigest()[:16]


def _find_group(state: dict, rec: dict) -> str | None:
    fp = rec.get("fp")
    ev = rec.get("eval") or {}
    for other in state["listings"].values():
        if other["id"] == rec["id"]:
            continue
        if fp and other.get("fp") == fp:
            return other["group"]
        oe = other.get("eval") or {}
        # Same flat on the other portal: same district, area and rent.
        if (other["source"] != rec["source"] and ev.get("area") and ev.get("rent")
                and oe.get("district") == ev.get("district")
                and oe.get("area") == ev.get("area") and oe.get("rent") == ev.get("rent")):
            return other["group"]
    return None


def upsert(state: dict, rec: dict, today: str) -> dict:
    """Insert or update a listing. Returns the stored record."""
    L = state["listings"]
    old = L.get(rec["id"])
    if old is None:
        rec["first_seen"] = today
        rec["price_history"] = [[today, rec.get("eval", {}).get("rent")]]
        rec["group"] = _find_group(state, rec) or rec["id"]
        L[rec["id"]] = rec
        stored = rec
    else:
        for k, v in rec.items():
            if v is not None and k not in ("first_seen", "price_history", "group"):
                old[k] = v
        rent = (rec.get("eval") or {}).get("rent")
        if rent is not None and old["price_history"][-1][1] != rent:
            old["price_history"].append([today, rent])
        stored = old
    stored.update(last_seen=today, missed_runs=0, active=True, removed_on=None)
    return stored


def mark_missing(state: dict, source: str, seen_ids: set[str], today: str) -> None:
    """Call only after a complete, successful crawl of `source`."""
    for rec in state["listings"].values():
        if rec["source"] != source or rec["id"] in seen_ids or not rec.get("active"):
            continue
        rec["missed_runs"] = rec.get("missed_runs", 0) + 1
        if rec["missed_runs"] >= config.REMOVED_AFTER_MISSES:
            rec["active"] = False
            rec["removed_on"] = today


def group_first_seen(state: dict, group: str) -> str:
    dates = []
    for r in state["listings"].values():
        if r["group"] == group:
            dates.append(r["first_seen"])
            if r.get("portal_date"):
                dates.append(r["portal_date"])
    return min(dates)


def days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days
