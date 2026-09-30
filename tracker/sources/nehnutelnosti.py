"""nehnutelnosti.sk: list pages -> cards, detail page -> full description.

Parsing is text-based (anchor links + visible text), not tied to CSS class
names, because the site uses generated class names that change often.
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from .. import config
from ..fetch import dump_debug
from ..textparse import norm

log = logging.getLogger(__name__)
SOURCE = "nehnutelnosti"
_DETAIL_RE = re.compile(r"/detail/([A-Za-z0-9_-]{6,})/")
_CONDITIONS = ("Kompletná rekonštrukcia", "Čiastočná rekonštrukcia", "Novostavba",
               "Pôvodný stav", "Vo výstavbe")


def _price(text: str) -> float | None:
    m = re.search(r"(\d[\d\s\u00a0]*)\s*€\s*/\s*mes", text)
    return float(re.sub(r"\D", "", m.group(1))) if m else None


# Main price "650 €/mes." (not the "13,83 €/m²/mes." line).
_MAIN_PRICE_RE = re.compile(r"\d[\d\s]*€\s*/\s*mes\.?")
# The portal's energy field directly under the price: "+ 150 €/mes. energie".
# \s also matches newlines, so it still works when the site renders the parts
# ("+", "150 €/mes.", "energie") in separate HTML elements.
_ENERGY_FIELD_RE = re.compile(r"\A\s*\+\s*(\d[\d\s]*?)\s*€\s*(?:/\s*mes\w*\.?)?\s*energi", re.I)


def _structured_energy(lines: list[str]) -> float | None:
    """The portal's own field, shown right under the rent as '+ 150 €/mes. energie'.

    Only the text immediately after the main price is checked, so amounts in
    the description or in 'similar listings' can't be picked up by mistake.
    """
    text = "\n".join(lines).replace("\u00a0", " ").replace("\u202f", " ").replace("\u200b", "")
    for m in _MAIN_PRICE_RE.finditer(text):
        after = text[m.end():m.end() + 80]
        e = _ENERGY_FIELD_RE.match(after)
        if e:
            return float(re.sub(r"\D", "", e.group(1)))
        return None  # only the first (main) price counts
    return None


def _location(lines: list[str]) -> str:
    for ln in lines:
        if re.search(r"Bratislava[- ]", ln) or "okres" in ln:
            return ln
    return ""


def parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _DETAIL_RE.search(href)
        if not m or "developersky-projekt" in href:
            continue
        nid = m.group(1)
        if nid in seen:
            continue
        seen.add(nid)
        # Climb to the largest ancestor that contains only this listing.
        node = a
        while node.parent is not None:
            others = [x for x in node.parent.find_all("a", href=True)
                      if (mm := _DETAIL_RE.search(x["href"])) and mm.group(1) != nid
                      and "developersky-projekt" not in x["href"]]
            if others:
                break
            node = node.parent
        lines = [ln for ln in node.get_text("\n", strip=True).split("\n") if ln.strip()]
        text = "\n".join(lines)
        title = next((ln for ln in lines if ln not in ("PREMIUM", "TOP", "NOVÉ") and len(ln) > 15), "")
        url = href if href.startswith("http") else "https://www.nehnutelnosti.sk" + href
        out.append({
            "id": f"{SOURCE}:{nid}",
            "source": SOURCE,
            "url": url.split("?")[0],
            "title": title,
            "location": _location(lines),
            "rent": _price(text),
            "card_text": text,
            "structured_condition": next((c for c in _CONDITIONS if c in lines), None),
            "structured_energy": _structured_energy(lines),
        })
    if not out:
        dump_debug("nehnutelnosti_list_empty.html", html)
    return out


def last_page(html: str) -> int:
    pages = [int(p) for p in re.findall(r"[?&]page=(\d+)", html)]
    return min(max(pages, default=1), config.NEHNUTELNOSTI_MAX_PAGES)


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "svg", "noscript"]):
        t.decompose()
    lines = [ln.strip() for ln in soup.get_text("\n", strip=True).split("\n") if ln.strip()]
    text = "\n".join(lines)

    desc = ""
    if "Popis nehnuteľnosti" in lines:
        start = lines.index("Popis nehnuteľnosti") + 1
        end = len(lines)
        for stop in ("Čítať ďalej", "Nenašli ste všetky informácie?", "Lokalita"):
            if stop in lines[start:]:
                end = min(end, lines.index(stop, start))
        desc = "\n".join(lines[start:end])

    # Parameters block ("Vlastnosti nehnuteľnosti" ... "Popis nehnuteľnosti")
    params = ""
    if "Vlastnosti nehnuteľnosti" in lines:
        s = lines.index("Vlastnosti nehnuteľnosti")
        params = "\n".join(lines[s:s + 40]).split("Popis nehnuteľnosti")[0]

    # Header block (title, parameters, price, energy field) ends where the
    # description starts; fall back to a generous fixed window.
    head_end = lines.index("Popis nehnuteľnosti") if "Popis nehnuteľnosti" in lines else 150
    head_lines = lines[:head_end]
    head = "\n".join(head_lines)
    agency = ("Profil realitnej kancelárie" in text) or ("MAKLÉR" in lines)
    private = bool(re.search(r"súkromn\w+ (?:inzerent|osoba|predajca)", text, re.I))
    if not desc:
        dump_debug("nehnutelnosti_detail_nodesc.html", html)
    return {
        "detail_text": (params + "\n" + desc).strip(),
        "structured_condition": next((c for c in _CONDITIONS if c in head.split("\n")), None),
        "is_agency": True if agency else (False if private else None),
        "location": _location(lines[:60]),
        "rent": _price(head),
        "structured_energy": _structured_energy(head_lines),
        "inactive": "Tento inzerát už nie je aktuálny." in text or "už nie je aktuálny" in text,
    }


def fetch_all(fetcher) -> tuple[list[dict], bool]:
    """Return (cards, complete). complete=False if any page failed."""
    first = fetcher.get(config.NEHNUTELNOSTI_LIST)
    if first is None:
        return [], False
    cards = parse_list(first)
    complete = bool(cards)
    for page in range(2, last_page(first) + 1):
        html = fetcher.get(config.NEHNUTELNOSTI_LIST, params={"page": page})
        if html is None:
            complete = False
            break
        batch = parse_list(html)
        if not batch:
            break
        cards.extend(batch)
    uniq = {c["id"]: c for c in cards}
    log.info("nehnutelnosti: %d cards (complete=%s)", len(uniq), complete)
    return list(uniq.values()), complete


def district_of(card: dict) -> str | None:
    m = re.search(r"Bratislava[- ]([^,]+)", card.get("location") or "")
    if not m:
        return None
    loc = norm(m.group(1))
    for name in config.DISTRICTS:
        if norm(name) in loc:
            return name
    return None
