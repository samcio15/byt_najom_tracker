"""Telegram alerts. Needs TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars."""
from __future__ import annotations

import html
import logging
import os

import requests

log = logging.getLogger(__name__)
MAX_LEN = 3900  # Telegram limit is 4096 characters


def _row(r: dict) -> str:
    e = r["eval"]
    bits = [e.get("district") or "?", f"{e['area']:g} m²" if e.get("area") else None,
            f"{e['floor']}. posch." if e.get("floor") is not None else None]
    line = f"<b>{e['effective']} €/mes.</b> " + ", ".join(b for b in bits if b)
    detail = f"nájom {e['rent']:.0f} €"
    detail += f" | energie {e['energy']:.0f} €" if e.get("energy") else (
        " | energie v cene" if e["energy_status"] == "included" else " | energie ?")
    detail += f" | provízia/12 {e['provision'] / 12:.0f} €" if e.get("provision") else " | provízia 0 €"
    warn = " ⚠️ " + "; ".join(e["flags"]) if e.get("flags") else ""
    return (f"{line}\n{html.escape(detail)}{html.escape(warn)}\n"
            f"<a href=\"{html.escape(r['url'])}\">{html.escape(r['title'][:70])}</a>")


def build_messages(new: list[dict], drops: list[tuple[dict, float]], new_check: int,
                   page_url: str | None, first_run_total: int | None = None) -> list[str]:
    parts = []
    if first_run_total is not None:
        parts.append(f"🏠 Tracker is running. {first_run_total} listings currently match or nearly match.")
    else:
        for r in new:
            tag = "🆕" if r["eval"]["status"] == "match" else "🟡 near miss"
            parts.append(f"{tag}\n{_row(r)}")
        for r, old in drops:
            parts.append(f"📉 price drop from {old:.0f} €\n{_row(r)}")
        if new_check:
            parts.append(f"🔍 {new_check} new listing(s) need a manual check.")
    if not parts:
        return []
    if page_url:
        parts.append(f"<a href=\"{html.escape(page_url)}\">Open full list</a>")
    msgs, cur = [], ""
    for p in parts:
        if len(cur) + len(p) + 2 > MAX_LEN:
            msgs.append(cur)
            cur = ""
        cur += p + "\n\n"
    if cur.strip():
        msgs.append(cur)
    return msgs


def send(messages: list[str]) -> None:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        log.info("Telegram not configured; would send %d message(s):", len(messages))
        for m in messages:
            log.info("\n%s", m)
        return
    for m in messages:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={
            "chat_id": chat, "text": m, "parse_mode": "HTML",
            "disable_web_page_preview": "true"}, timeout=20)
        if not r.ok:
            log.error("Telegram error %s: %s", r.status_code, r.text[:300])
