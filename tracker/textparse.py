"""Extract listing facts from Slovak free text.

Every function works on text normalised by `norm()` (lowercase, no diacritics)
and returns None when the text does not say, so callers can tell
"unknown" apart from "no".
"""
from __future__ import annotations

import re
import unicodedata

from . import config

# --------------------------------------------------------------------------- #
# Normalisation
# --------------------------------------------------------------------------- #

def norm(text: str | None) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower().replace("\u00a0", " ").replace("\u202f", " ")
    t = re.sub(r"\b(eur|euro|eurami|eur\.)\b", "€", t)
    t = re.sub(r"\bplus\b", "+", t)
    t = re.sub(r"(?<=\d) (?=\d{3}\b)", "", t)       # "1 050" -> "1050"
    t = re.sub(r"(?<=\d)[.,]-", "", t)               # "650,-" -> "650"
    t = re.sub(r"(?<=\d),00\b", "", t)               # "650,00" -> "650"
    t = re.sub(r"[ \t]+", " ", t)
    return t


def _first(patterns, text):
    """Earliest match across patterns -> (match, pattern_index) or (None, None)."""
    best = None
    for i, p in enumerate(patterns):
        m = re.search(p, text)
        if m and (best is None or m.start() < best[0].start()):
            best = (m, i)
    return best if best else (None, None)


# --------------------------------------------------------------------------- #
# Rooms
# --------------------------------------------------------------------------- #

_ROOM_PATTERNS = [
    (r"dvoj\s*-?\s*gars[oa]n|dvojgarz[oa]n|\b2\s*-?\s*gars[oa]n", lambda m: 1.9),
    (r"\b([1-4])\s*[,.]\s*5\s*[-–]?\s*(?:izb|i\b)", lambda m: float(m.group(1)) + 0.5),
    (r"\bgars[oa]n|\bgarz[oa]n|\bstudio\b", lambda m: 1),
    (r"\bjedno\s*izb", lambda m: 1),
    (r"\bdvoj\s*izb|\bdvojka\b", lambda m: 2),
    (r"\btroj\s*izb", lambda m: 3),
    (r"\bstvor\s*izb", lambda m: 4),
    (r"\b([1-6])\s*[-–.]?\s*izb", lambda m: int(m.group(1))),
    (r"\b([1-6])\s*\+\s*(?:kk|1)\b", lambda m: int(m.group(1))),
]


def rooms(title: str, text: str = "") -> float | None:
    for src in (norm(title), norm(text)):
        best = None
        for pat, fn in _ROOM_PATTERNS:
            m = re.search(pat, src)
            if m and (best is None or m.start() < best[0].start()):
                best = (m, fn)
        if best:
            return best[1](best[0])
    return None


# --------------------------------------------------------------------------- #
# Floor  (Slovak: prizemie = 0, 1. poschodie = first floor above ground)
# --------------------------------------------------------------------------- #

_ORDINALS = {"prv": 1, "druh": 2, "tret": 3, "stvrt": 4, "piat": 5, "siest": 6,
             "siedm": 7, "osm": 8, "devat": 9, "desiat": 10}


_FLOOR_OF_TOTAL = [
    r"poschodi\w*\s*:?\s*(\d{1,2})\s*/\s*(\d{1,2})(?!\d)",
    r"\b(\d{1,2})\s*\.?\s*p\s*\.?\s*/\s*(\d{1,2})(?!\d)",
    r"\b(\d{1,2})\s*/\s*(\d{1,2})\s*\.?\s*(?:posch\w*|p\b)",
    r"\b(\d{1,2})\s*\.?\s*posch\w*\s*\.?\s*/\s*(\d{1,2})(?!\d)",
    r"\b(\d{1,2})\s*\.?\s*z[o]?\s+(\d{1,2})\s*\.?\s*(?:poschod|nadzemn)",
]


def portal_floor(value: str | None) -> int | None:
    """nehnutelnosti.sk 'Podlažie' / 'Umiestnenie' field -> poschodie.

    '1/6 + výťah' -> 1, '4/5' -> 4, 'Prízemie' -> 0. The portal field counts
    like 'poschodie' (the ads' own text, e.g. '1p./6p.', agrees with it).
    'Ďalšie nadzemné podlažie' / 'Posledné podlažie' don't give a number -> None.
    """
    v = norm(value).strip()
    if not v:
        return None
    if re.search(r"\bprizem|\bsuteren", v):
        return 0
    m = re.match(r"(-?\d{1,2})\s*(?:/\s*\d{1,2})?\b", v)
    return int(m.group(1)) if m else None


def floor(text: str, structured: str | None = None) -> tuple[int | None, str]:
    """Return (poschodie, note). note explains ambiguity.

    `structured` is the portal's own floor field; when it gives a number it wins.
    """
    pf = portal_floor(structured)
    if pf is not None:
        return pf, ""
    t = norm(text)
    candidates = []  # (position, value, note)

    for m in re.finditer(r"(\d{1,2})\s*\.\s*(?:poschod|posch\b)|(\d{1,2})\s+poschod(?!ov)", t):
        candidates.append((m.start(), int(m.group(1) or m.group(2)), ""))
    for m in re.finditer(r"poschodie\s*:\s*(\d{1,2})", t):
        candidates.append((m.start(), int(m.group(1)), ""))
    # "X/Y" forms, where the first number is the floor:
    #   "poschodie 1/5", "poschodie: 10 / 13", "1p./6p.", "5. p. / 7 p.", "3p/4.",
    #   "12/12 posch.", "8/8posch.", "2/4p.", "12/21 p.", "3posch./10", "5. zo 7 poschodí"
    for pat in _FLOOR_OF_TOTAL:
        for m in re.finditer(pat, t):
            fl, total = int(m.group(1)), int(m.group(2))
            if fl <= total <= 40:
                candidates.append((m.start(), fl, ""))
    for m in re.finditer(r"\b(\d{1,2})\s*-?\s*(?:tom|om|ho)\s+poschod", t):   # "10-tom poschodí"
        candidates.append((m.start(), int(m.group(1)), ""))
    for m in re.finditer(r"(\d{1,2})\s*\.?\s*np\b", t):          # nadzemne podlazie
        candidates.append((m.start(), int(m.group(1)) - 1, ""))
    for m in re.finditer(r"(\d{1,2})\s*\.\s*(?:nadzemn\w* )?podlaz", t):
        n = int(m.group(1))
        # "podlazie" is used both ways; only trust it when both readings agree.
        if n - 1 >= config.MIN_FLOOR:
            candidates.append((m.start(), n - 1, ""))
        elif n < config.MIN_FLOOR:
            candidates.append((m.start(), n, ""))
        else:
            candidates.append((m.start(), None, f"'{n}. podlažie' is ambiguous"))
    for m in re.finditer(r"\b(" + "|".join(_ORDINALS) + r")\w*\s+(?:poschod|nadzemn)", t):
        candidates.append((m.start(), _ORDINALS[m.group(1)], ""))

    if candidates:
        candidates.sort(key=lambda c: c[0])
        _, val, note = candidates[0]
        return val, note
    if re.search(r"\bprizem|\bsuteren|\bsuterenn", t):
        return 0, ""
    return None, ""


# --------------------------------------------------------------------------- #
# Balcony
# --------------------------------------------------------------------------- #

def balcony(text: str) -> bool | None:
    t = norm(text)
    t = re.sub(r"francuzsk\w*\s+(?:balkon\w*|okn\w*|dver\w*)", " ", t)
    if re.search(r"\bbez\s+(?:balkon|lodzi|loggi|terasy)|\bnema\s+(?:ziaden\s+)?(?:balkon|lodzi)"
                 r"|balkon\w*\s*:\s*nie", t):
        return False
    if re.search(r"balkon|lodzi|lodza|loggi|terasa|terasou|terasy\b|teras\w*", t):
        return True
    return None


# --------------------------------------------------------------------------- #
# Condition
# --------------------------------------------------------------------------- #

_STRUCTURED_CONDITION = {
    "kompletna rekonstrukcia": "renovated",
    "ciastocna rekonstrukcia": "partial",
    "novostavba": "new",
    "povodny stav": "original",
    "vo vystavbe": "original",
    "developersky projekt": "new",
}


def condition(text: str, structured: str | None = None) -> str | None:
    """'renovated' | 'partial' | 'new' | 'original' | None"""
    if structured:
        s = norm(structured).strip()
        for key, val in _STRUCTURED_CONDITION.items():
            if key in s:
                return val
    t = norm(text)
    negative = re.search(
        r"povodn\w* stav|povodnom stave|pred rekonstrukci|(?:vhodn\w*|urcen\w*) na rekonstrukci"
        r"|(?:potrebuje|vyzaduje|nutn\w*)\s+(?:\w+\s+)?rekonstrukci", t)
    if re.search(r"novostavb|nov\w* bytov\w* dom|nov\w* projekt", t):
        return "new"
    if re.search(r"ciastocn\w*\s+(?:zre|re)konstru|ciastocne prerob", t):
        return "partial"
    full = re.search(
        r"(?:kompletn\w*|celkov\w*|komplet\w*|luxusn\w*|nedavn\w*|citliv\w*|nov\w*)\s+(?:zre|re)konstru"
        r"|po\s+(?:kompletnej\s+|celkovej\s+|novej\s+|nedavnej\s+)?rekonstrukci"
        r"|zrekonstruovan|prerobe|renovovan|kompletne prerob|presiel\w*\s+(?:\w+\s+)?rekonstrukci", t)
    if full:
        return "partial" if negative else "renovated"
    if re.search(r"rekonstru", t) and not negative:
        return "partial"
    if negative:
        return "original"
    return None


# --------------------------------------------------------------------------- #
# Energies
# --------------------------------------------------------------------------- #

_KW = (r"(?:sluzb\w*\s+a\s+energi\w*|energi\w*|zaloh\w*|sluzb\w* spojen\w*"
       r"|mesacn\w* poplat\w*|poplatk\w* za (?:energie|sluzby|byt))")
_NUM = r"(\d{2,3})(?:\s*[-–]\s*(\d{2,3}))?\s*€"
_PER = r"(?:\s*/\s*mes\w*\.?|\s*mesacne|\s*mes\.)?"
# Between the amount and the keyword: "230 € energie", "230 € na energie",
# and the slash form "230 Eur/energie" or "180 €/mes./energie".
_SEP = r"\s*/?\s*(?:na\s+|za\s+)?"

_ENERGY_PLUS = [
    r"\+\s*(?:cca\s*|priblizne\s*|okolo\s*)?" + _NUM + r"\w*" + _PER + _SEP + _KW,
    r"\+\s*" + _KW + r"[^\d.]{0,20}?" + _NUM,
]
_ENERGY_PLAIN = [
    _KW + r"[^\d.+]{0,25}?" + _NUM,
    _NUM + r"\w*" + _PER + _SEP + _KW,
]
_ENERGY_INCLUDED = (
    r"vrat(?:ane|\.)\s+(?:vsetk\w*\s+)?(?:energi|poplatk|sluzieb|zaloh)"
    r"|energie\s+(?:su\s+)?(?:v cene|zahrnut\w*\s+v\s+(?:cene|najm)|v najm)"
    r"|v cene\s+(?:su\s+|je\s+)?(?:aj\s+)?(?:vsetky\s+)?energi"
    r"|(?:spolu|aj|so|s)\s+(?:vsetkymi\s+)?energiami|vcetne energi|all\s?inclusive"
)


def _energy_amount(patterns, t):
    """First plausible energy amount across all patterns, by position in text."""
    found = []
    for p in patterns:
        for m in re.finditer(p, t):
            lo = int(m.group(1))
            hi = int(m.group(2)) if m.group(2) else lo
            found.append((m.start(), max(lo, hi)))  # ranges: use the upper bound
    for _, val in sorted(found):
        if config.ENERGY_MIN <= val <= config.ENERGY_MAX:
            return val
    return None


def _included_matches(t: str):
    """'vrátane energií' and similar, skipping negated forms ('nie je vrátane', 'bez')."""
    for m in re.finditer(_ENERGY_INCLUDED, t):
        before = t[max(0, m.start() - 14):m.start()]
        if re.search(r"\b(?:nie|bez|nezahrn\w*|neobsahuj\w*)\b", before):
            continue
        yield m


def energies(text: str, rent: float | None = None) -> dict:
    """
    {'status': 'included' | 'total' | 'separate' | 'guessed' | 'unknown', 'amount': int|None}

    'included' and 'total' come from "vrátane energií" wording, which overrules
    everything else (also the portal's energy field):
      - "700 € vrátane energií" with rent 700      -> included, energies 0
      - "850 € vrátane energií" with listed rent 700 -> total 850, energies 150
    """
    t = norm(text)
    inc = list(_included_matches(t))
    if inc:
        if rent:
            for m in re.finditer(r"\b(\d{3,4})\s*€[^.\d]{0,30}$", t[:inc[0].start()]):
                total = int(m.group(1))
                if total > rent and total - rent <= config.ENERGY_MAX:
                    return {"status": "total", "amount": total - int(rent)}
            for m in inc[1:]:
                pre = re.search(r"\b(\d{3,4})\s*€[^.\d]{0,30}$", t[:m.start()])
                if pre and int(pre.group(1)) > rent and int(pre.group(1)) - rent <= config.ENERGY_MAX:
                    return {"status": "total", "amount": int(pre.group(1)) - int(rent)}
        return {"status": "included", "amount": 0}
    plus = _energy_amount(_ENERGY_PLUS, t)
    amount = plus if plus is not None else _energy_amount(_ENERGY_PLAIN, t)
    if amount is not None:
        return {"status": "separate", "amount": amount}
    guess = _guess_energy(t)
    if guess is not None:
        return {"status": "guessed", "amount": guess}
    return {"status": "unknown", "amount": None}


# Words that mean a nearby amount is NOT energies.
_NOT_ENERGY = (r"park|garaz|stati|provizi|depozit|kauci|zabezpec|\bpes\b|\bpsa\b|zviera"
               r"|kobk|pivnic|€\s*/\s*m|m2|vybav|nabyt|upratov|cistenie")


def _guess_energy(t: str) -> int | None:
    """Fallback: an amount of 100-300 EUR anywhere in the text is taken as energies,
    unless the words around it say it's parking, deposit, provision, etc."""
    for m in re.finditer(r"(?<![\d.,])(\d{3})\s*€", t):
        val = int(m.group(1))
        if not config.ENERGY_GUESS_MIN <= val <= config.ENERGY_GUESS_MAX:
            continue
        window = t[max(0, m.start() - 45):m.end() + 30]
        if re.search(_NOT_ENERGY, window):
            continue
        return val
    return None


# --------------------------------------------------------------------------- #
# Agency / provision
# --------------------------------------------------------------------------- #

_NO_PROVISION = (
    r"bez\s+(?:rk\b|provizi\w*|realitk\w*|realitn\w*\s+kancelari\w*|sprostredkovat\w*|poplatk\w*\s+rk)"
    r"|\bnie\s+(?:som\s+|sme\s+)?(?:rk\b|realitka|realitna kancelaria)"
    r"|\b(?:rk|realitky|realitne kancelarie)\b[^.]{0,20}(?:nevolat|nekontaktovat|neotravovat|prosim nie)"
    r"|priamo\s+od\s+(?:majitel|vlastnik)|sukromn\w*\s+(?:osob|inzer|majitel)"
    r"|(?:nekontaktoval\w*|nevolal\w*|nevolajte|nekontaktujte)\s+(?:ma\s+|nas\s+)?(?:\w+\s+)?(?:rk\b|realitn|realitk)"
    r"|provizi\w*\s+(?:je\s+)?(?:0\b|nulov|ziadn)|ziadn\w*\s+provizi|nulov\w*\s+provizi"
    r"|provizi\w*\s+(?:sa\s+)?(?:neplat|neuctuj|nebude)|neplati\w*\s+(?:sa\s+)?(?:ziadn\w*\s+)?provizi"
)
_AGENCY = (
    r"\brk\b|realitn\w*\s+kancelari|realitk\w*|makler\w*|provizi\w*|sprostredkovat"
    r"|exkluzivn\w*\s+(?:vam\s+)?ponuk|\breality\b|\bs\.\s?r\.\s?o\b"
)


def agency_signals(text: str) -> bool:
    t = norm(text)
    t = re.sub(_NO_PROVISION, " ", t)
    return re.search(_AGENCY, t) is not None


def provision(text: str, rent: float | None, is_agency: bool | None) -> dict:
    """{'amount': float|None, 'source': 'none'|'stated'|'assumed'|'private'}"""
    t = norm(text)
    if re.search(_NO_PROVISION, t):
        return {"amount": 0.0, "source": "none"}

    for m in re.finditer(r"provizi\w*([^.]{0,45}?)(\d{3,4})\s*€|(\d{3,4})\s*€\w*\s+provizi", t):
        between = m.group(1) or ""
        if re.search(r"depozit|kauci|zabezpec|zalohu", between):
            continue
        return {"amount": float(m.group(2) or m.group(3)), "source": "stated"}

    m = re.search(
        r"provizi\w*[^.]{0,60}?(jedn\w*|1|dvoj\w*|2|polovic\w*|50\s*%|100\s*%)[\s-]*"
        r"(?:\w+\s+){0,2}?(?:najm|najomn|mesiac|mesacn)", t)
    if not m:
        m = re.search(r"provizi\w*[^.]{0,40}?vo\s+vyske\s+(?:\w+\s+)?(najm|najomn)", t)
    if m and rent:
        token = m.group(1)
        months = 1.0
        if token.startswith(("dvoj", "2")):
            months = 2.0
        elif token.startswith(("polovic", "50")):
            months = 0.5
        return {"amount": months * rent, "source": "stated"}

    agency = is_agency if is_agency is not None else agency_signals(text)
    if agency and rent:
        return {"amount": config.DEFAULT_PROVISION_MONTHS * rent, "source": "assumed"}
    return {"amount": 0.0, "source": "private"}


# --------------------------------------------------------------------------- #
# District
# --------------------------------------------------------------------------- #

def district_from_text(*texts: str) -> str | None:
    for raw in texts:
        t = norm(raw)
        best = None
        for name, pats in config.DISTRICTS.items():
            for p in pats:
                m = re.search(p, t)
                if m and (best is None or m.start() < best[0]):
                    best = (m.start(), name)
        if best:
            return best[1]
    return None


def district_from_postcode(pc: str | None) -> str | None:
    if not pc:
        return None
    pc = re.sub(r"\D", "", pc)
    for name, codes in config.POSTCODES.items():
        if pc in codes:
            return name
    return None


# --------------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------------- #

def is_unavailable(title: str) -> bool:
    """Title marks the flat as already reserved or rented."""
    return re.search(r"\b(rezervovan\w*|prenajat\w*|obsaden\w*)\b", norm(title)) is not None


def is_wanted_ad(title: str) -> bool:
    """False for 'looking for a flat' posts on Bazos."""
    t = norm(title).strip()
    return not re.match(r"(hladam|hladame|zhanam|kupim|prenajmem si|hlada sa)\b", t)


def rent_from_text(text: str) -> float | None:
    t = norm(text)
    m = re.search(r"(?:najom\w*|cena\w*)[^.\d]{0,25}?(\d{3,4})\s*€", t)
    return float(m.group(1)) if m else None


def area_m2(text: str) -> float | None:
    t = norm(text)
    m = re.search(r"(\d{2,3}(?:[.,]\d{1,2})?)\s*(?:m2|m²|m\^2|metrov)", t)
    return float(m.group(1).replace(",", ".")) if m else None
