"""reality.bazos.sk: flats for rent around Bratislava."""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from .. import config
from ..fetch import dump_debug

log = logging.getLogger(__name__)
SOURCE = "bazos"
_ID_RE = re.compile(r"/inzerat/(\d+)/")


def _date(text: str) -> str | None:
    m = re.search(r"\[(\d{1,2})\.(\d{1,2})\.\s*(\d{4})\]", text or "")
    if not m:
        return None
    d, mo, y = map(int, m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def _price(text: str) -> float | None:
    digits = re.sub(r"\D", "", text or "")
    return float(digits) if digits and "€" in (text or "") and int(digits) > 0 else None


def parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for box in soup.select("div.inzeraty"):
        a = box.select_one("h2.nadpis a") or box.select_one("a[href*='/inzerat/']")
        if not a:
            continue
        m = _ID_RE.search(a["href"])
        if not m:
            continue
        loc_el = box.select_one(".inzeratylok")
        loc_parts = list(loc_el.stripped_strings) if loc_el else []
        postcode = next((p for p in loc_parts if re.fullmatch(r"\d{3}\s?\d{2}", p)), None)
        desc = box.select_one(".popis")
        meta = box.select_one(".velikost10")
        out.append({
            "id": f"{SOURCE}:{m.group(1)}",
            "source": SOURCE,
            "url": a["href"],
            "title": a.get_text(strip=True),
            "location": " ".join(loc_parts),
            "postcode": postcode.replace(" ", "") if postcode else None,
            "rent": _price(box.select_one(".inzeratycena").get_text(" ", strip=True)
                           if box.select_one(".inzeratycena") else ""),
            "card_text": desc.get_text(" ", strip=True) if desc else "",
            "portal_date": _date(meta.get_text(" ", strip=True) if meta else ""),
        })
    return out


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    desc = soup.select_one(".popisdetail")
    head = soup.select_one(".inzeratydetnadpis")
    info = soup.select_one(".listadvlevo")
    info_text = info.get_text(" ", strip=True) if info else ""
    pc = re.search(r"Lokalita:\s*(\d{3}\s?\d{2})", info_text)
    price = re.search(r"Cena:\s*([^\n]+?€)", info_text)
    if not desc:
        dump_debug("bazos_detail_nodesc.html", html)
    return {
        "detail_text": desc.get_text("\n", strip=True) if desc else "",
        "portal_date": _date(head.get_text(" ", strip=True) if head else ""),
        "postcode": pc.group(1).replace(" ", "") if pc else None,
        "rent": _price(price.group(1)) if price else None,
        "location": info_text.split("Lokalita:")[-1].split("Videlo")[0].strip() if "Lokalita:" in info_text else "",
    }


def page_url(page: int) -> str:
    return config.BAZOS_BASE if page == 0 else f"{config.BAZOS_BASE}{page * config.BAZOS_PAGE_SIZE}/"


def fetch_all(fetcher) -> tuple[list[dict], bool]:
    cards, complete = [], True
    for page in range(config.BAZOS_MAX_PAGES):
        html = fetcher.get(page_url(page), params=config.BAZOS_PARAMS)
        if html is None:
            complete = False
            break
        batch = parse_list(html)
        if not batch:
            if page == 0:
                dump_debug("bazos_list_empty.html", html)
                complete = False
            break
        new = [c for c in batch if c["id"] not in {x["id"] for x in cards}]
        if not new:
            break
        cards.extend(new)
        if len(batch) < config.BAZOS_PAGE_SIZE:
            break
    log.info("bazos: %d cards (complete=%s)", len(cards), complete)
    return cards, complete
