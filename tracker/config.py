"""All tunable settings live here. Edit this file, not the code."""

# ---- Price rules (EUR per month) -------------------------------------------
MAX_EFFECTIVE = 800          # main list: rent + energies + provision/12 <= this
NEAR_MISS_MAX = 820          # near-miss section: MAX_EFFECTIVE < effective <= this
MIN_RENT_PLUS_ENERGIES = 600 # below this = suspicious, dropped
CONTRACT_MONTHS = 12         # provision is spread over this many months
DEFAULT_PROVISION_MONTHS = 1.0  # agency listing, provision not stated -> assume 1x rent

# Plausible range for a stated energy amount; outside it we ignore the number.
ENERGY_MIN, ENERGY_MAX = 40, 450
# Fallback when energies are not named: any amount in this range in the text
# (not next to words like parking, deposit, provision) is taken as energies.
ENERGY_GUESS_MIN, ENERGY_GUESS_MAX = 100, 300

# ---- Flat rules -------------------------------------------------------------
ROOMS = 2
MIN_FLOOR = 2                # 2. poschodie and higher (prizemie = 0)
# Dvojgarsonka = two small rooms. Portals list it as 2-room.
# "flag" = keep it but mark it, "exclude" = drop it, "accept" = treat as normal 2-room.
DVOJGARSONKA = "accept"

# Bump when parsing changes, so stored listings get their detail page re-read once.
PARSER_VERSION = 4

# ---- Districts --------------------------------------------------------------
# Regexes run on lowercase text with diacritics removed.
# Order matters only for display. Sub-area names help with Bazos free text.
DISTRICTS = {
    "Petržalka":   [r"petrzal\w*", r"\bovsist\w*"],
    "Ružinov":     [r"ruzinov\w*", r"\bprievoz\w*", r"\btrnavk\w*", r"\bstrkovc\w*|\bstrkovec",
                    r"\bostredk\w*", r"\bposen\w*", r"\bmlynske nivy"],
    "Karlova Ves": [r"karlov\w* ves\w*", r"karlovej vsi", r"\bdlhe diely|\bdlhych dieloch"],
    "Nové Mesto":  [r"\bnov(e|om|eho|ym) mest(o|e|a|u|om)\b(?! nad)", r"\bkolib\w*", r"\bkramar\w*",
                    r"\bkuchajd\w*", r"\bpasienk\w*", r"jurajov\w* dvor\w*"],
    "Rača":        [r"\brac(a|i|e|u|ou)\b", r"\bkrasnan\w*"],
}

# Bazos postal codes -> district. Best-effort mapping; verify and adjust.
# Deliberately excluded: 821 06 Podunajske Biskupice, 821 07 Vrakuna.
POSTCODES = {
    "Petržalka":   ["85101", "85102", "85103", "85104", "85105", "85106", "85107"],
    "Ružinov":     ["82101", "82102", "82103", "82104", "82105", "82108", "82109"],
    "Karlova Ves": ["84104"],
    "Nové Mesto":  ["83101", "83102", "83103", "83104"],
    "Rača":        ["83106"],
}

# ---- Sources ----------------------------------------------------------------
NEHNUTELNOSTI_LIST = "https://www.nehnutelnosti.sk/vysledky/2-izbove-byty/bratislava/prenajom"
NEHNUTELNOSTI_MAX_PAGES = 40

# Bazos: flats for rent within 15 km of Bratislava center, price <= near-miss cap.
BAZOS_BASE = "https://reality.bazos.sk/prenajmu/byt/"
BAZOS_PARAMS = {
    "hledat": "", "rubriky": "reality", "hlokalita": "81101", "humkreis": "15",
    "cenaod": "", "cenado": str(NEAR_MISS_MAX), "order": "", "kitx": "ano",
}
BAZOS_PAGE_SIZE = 20
BAZOS_MAX_PAGES = 40

# ---- Politeness -------------------------------------------------------------
REQUEST_DELAY = (2.0, 4.5)   # random pause between requests, seconds
TIMEOUT = 25
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

# A listing is marked removed after it is missing this many successful runs in a row.
REMOVED_AFTER_MISSES = 2
