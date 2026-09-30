"""Daily run: crawl -> prefilter -> detail -> evaluate -> history -> alert -> page.

Usage:
  python -m tracker.main                 # live run
  python -m tracker.main --offline DIR   # use saved HTML fixtures (testing)
"""
from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import config, notify, render, store
from . import textparse as tp
from .evaluate import evaluate
from .fetch import Fetcher
from .sources import bazos, nehnutelnosti

log = logging.getLogger("tracker")
SOURCES = {nehnutelnosti.SOURCE: nehnutelnosti, bazos.SOURCE: bazos}
REMOVED_WINDOW_DAYS = 30


# --------------------------------------------------------------------------- #
# Prefilter: cheap checks on list cards before fetching detail pages
# --------------------------------------------------------------------------- #

def prefilter(card: dict) -> bool:
    rent = card.get("rent")
    if rent is not None and rent > config.NEAR_MISS_MAX:
        return False
    if card["source"] == nehnutelnosti.SOURCE:
        return nehnutelnosti.district_of(card) is not None
    if not tp.is_wanted_ad(card["title"]) or tp.is_unavailable(card["title"]):
        return False
    if tp.rooms(card["title"], card.get("card_text", "")) not in (config.ROOMS, 1.9, None):
        return False
    pc = card.get("postcode") or ""
    return not pc or pc[:2] in ("81", "82", "83", "84", "85")


# --------------------------------------------------------------------------- #
# Offline fetcher for tests / demo
# --------------------------------------------------------------------------- #

class FixtureFetcher:
    def __init__(self, folder: Path):
        self.f = folder

    def get(self, url, params=None):
        page = (params or {}).get("page")
        if "nehnutelnosti.sk/vysledky" in url:
            return None if page else (self.f / "nehn_list.html").read_text(encoding="utf-8")
        if "nehnutelnosti.sk/detail/JunEjsigkpx" in url:
            return (self.f / "nehn_detail.html").read_text(encoding="utf-8")
        if url == config.BAZOS_BASE:
            return (self.f / "bazos_list.html").read_text(encoding="utf-8")
        if "/inzerat/195892150/" in url:
            return (self.f / "bazos_detail.html").read_text(encoding="utf-8")
        return None


# --------------------------------------------------------------------------- #
# View model for page + alerts
# --------------------------------------------------------------------------- #

RANK = {"match": 0, "near": 1, "check": 2, "excluded": 3}


def build_rows(state: dict, today: str) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for r in state["listings"].values():
        groups.setdefault(r["group"], []).append(r)
    rows = []
    cutoff = (date.fromisoformat(today) - timedelta(days=REMOVED_WINDOW_DAYS)).isoformat()
    for gid, recs in groups.items():
        active = [r for r in recs if r.get("active")]
        if active:
            rep = min(active, key=lambda r: (RANK[r["eval"]["status"]], len(r["eval"]["unknown"])))
            section = rep["eval"]["status"]
            end = today
        else:
            rep = max(recs, key=lambda r: r.get("removed_on") or "")
            if (rep.get("removed_on") or "") < cutoff or rep["eval"]["status"] == "excluded":
                continue
            section, end = "removed", rep["removed_on"]
        e = rep["eval"]
        rows.append({
            "section": section, "title": rep["title"], "district": e["district"],
            "area": e["area"], "floor": e["floor"], "balcony": e["balcony"],
            "condition": e["condition"], "rent": e["rent"], "energy": e["energy"],
            "energy_status": e["energy_status"], "provision": e["provision"],
            "effective": e["effective"], "flags": e["flags"], "unknown": e["unknown"],
            "excluded": e["excluded"], "history": rep["price_history"],
            "days": store.days_between(store.group_first_seen(state, gid), end),
            "links": [{"source": r["source"], "url": r["url"]}
                      for r in sorted(recs, key=lambda r: not r.get("active"))],
            "group": gid,
        })
    return rows


def diff_alerts(state: dict, rows: list[dict], today: str):
    notified = set(state.get("notified", []))
    new, new_check = [], 0
    by_group = {r["group"]: r for r in rows}
    for gid, row in by_group.items():
        if row["section"] in ("match", "near") and gid not in notified:
            rec = state["listings"].get(gid) or next(
                r for r in state["listings"].values() if r["group"] == gid)
            new.append({**rec, "url": row["links"][0]["url"]})
            notified.add(gid)
        elif row["section"] == "check" and gid + ":check" not in notified:
            new_check += 1
            notified.add(gid + ":check")
    drops = []
    for rec in state["listings"].values():
        h = rec["price_history"]
        if (rec.get("active") and len(h) >= 2 and h[-1][0] == today and h[-1][1] and h[-2][1]
                and h[-1][1] < h[-2][1] and rec["eval"]["status"] in ("match", "near", "check")
                and rec["group"] in notified):
            drops.append((rec, h[-2][1]))
    state["notified"] = sorted(notified)
    return new, drops, new_check


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def run(fetcher, today: str, send_alerts: bool = True) -> dict:
    state = store.load()
    first_run = not state["runs"]
    run_info = {"date": today, "sources": {}}
    warnings = []

    for name, mod in SOURCES.items():
        cards, complete = mod.fetch_all(fetcher)
        if not cards:
            warnings.append(f"⚠️ {name} returned no listings. The site may be blocking the "
                            "tracker or changed its layout; see data/debug in the run artifacts.")
        seen = {c["id"] for c in cards}
        details = 0
        for card in cards:
            old = state["listings"].get(card["id"])
            if old is None and not prefilter(card):
                continue
            rec = dict(card)
            need_detail = (old is None or not old.get("detail_text")
                           or old.get("rent") != card.get("rent")
                           or old.get("parser_version") != config.PARSER_VERSION)
            if need_detail and (old is not None or prefilter(card)):
                html = fetcher.get(card["url"])
                details += 1
                if html:
                    d = mod.parse_detail(html)
                    rec.update({k: v for k, v in d.items() if v not in (None, "")})
            elif old:
                for k in ("detail_text", "is_agency", "structured_condition", "structured_energy",
                          "inactive", "postcode", "portal_date"):
                    rec.setdefault(k, old.get(k))
                    if rec.get(k) in (None, ""):
                        rec[k] = old.get(k)
            if need_detail:
                rec["parser_version"] = config.PARSER_VERSION
            rec["eval"] = evaluate(rec)
            rec["fp"] = store.fingerprint(rec.get("detail_text") or "")
            store.upsert(state, rec, today)
        if complete:
            store.mark_missing(state, name, seen, today)
        run_info["sources"][name] = {"cards": len(cards), "complete": complete, "details": details}
        log.info("%s: %d cards, %d detail pages, complete=%s", name, len(cards), details, complete)

    # Re-evaluate everything so rule changes in config apply to old listings too.
    for rec in state["listings"].values():
        rec["eval"] = evaluate(rec)

    rows = build_rows(state, today)
    new, drops, new_check = diff_alerts(state, rows, today)
    if send_alerts:
        page = os.getenv("PAGE_URL")
        if first_run:
            total = sum(1 for r in rows if r["section"] in ("match", "near"))
            msgs = notify.build_messages([], [], 0, page, first_run_total=total)
        else:
            msgs = notify.build_messages(new, drops, new_check, page)
        notify.send(warnings + msgs)

    state["runs"] = (state["runs"] + [run_info])[-60:]
    store.save(state)
    stamp = datetime.now(timezone.utc).astimezone().strftime("%-d %b %Y, %H:%M")
    render.render(rows, stamp)
    counts = {s: sum(1 for r in rows if r["section"] == s) for s in ("match", "near", "check", "removed", "excluded")}
    log.info("Done: %s", counts)
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", type=Path, help="folder with saved HTML fixtures")
    ap.add_argument("--no-alerts", action="store_true")
    ap.add_argument("--today", help="override date (YYYY-MM-DD), for testing")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    fetcher = FixtureFetcher(a.offline) if a.offline else Fetcher()
    run(fetcher, a.today or date.today().isoformat(), send_alerts=not a.no_alerts)


if __name__ == "__main__":
    main()
