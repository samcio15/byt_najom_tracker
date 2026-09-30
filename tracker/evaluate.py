"""Turn a raw listing into a verdict: match / near / check / excluded."""
from __future__ import annotations

from . import config
from . import textparse as tp
from .sources import nehnutelnosti


def district(rec: dict) -> tuple[str | None, str]:
    """(district, how) — how is 'portal', 'postcode' or 'text'."""
    if rec["source"] == nehnutelnosti.SOURCE:
        return nehnutelnosti.district_of(rec), "portal"
    by_pc = tp.district_from_postcode(rec.get("postcode"))
    if by_pc:
        return by_pc, "postcode"
    by_text = tp.district_from_text(rec.get("title", ""), rec.get("location", ""),
                                    rec.get("detail_text") or rec.get("card_text", ""))
    return by_text, "text"


def evaluate(rec: dict) -> dict:
    title = rec.get("title", "")
    body = rec.get("detail_text") or rec.get("card_text", "")
    full = f"{title}\n{body}"

    excluded, unknown, flags = [], [], []

    if rec.get("inactive") or tp.is_unavailable(title):
        excluded.append("reserved or no longer available")

    dist, how = district(rec)
    if not dist:
        excluded.append("district not on your list")
    elif how == "text":
        flags.append("district guessed from text")

    rooms = tp.rooms(title, body)
    if rec["source"] == nehnutelnosti.SOURCE and rooms is None:
        # fall back to the portal category the card came from
        rooms = 1 if rec.get("list_category") == "1" else 2
    if rooms == 1.9:  # dvojgarsonka
        if config.DVOJGARSONKA == "exclude":
            excluded.append("dvojgarsónka")
        elif config.DVOJGARSONKA == "flag":
            flags.append("dvojgarsónka (two small rooms)")
        rooms = 2
    one_and_half = rooms == 1.5 and config.ONE_AND_HALF_ROOMS == "separate"
    if rooms is None:
        unknown.append("rooms")
    elif rooms != config.ROOMS and not one_and_half:
        excluded.append(f"{rooms:g} rooms")

    # Portal floor field (nehnutelnosti "Podlažie: 1/6") first, then the text.
    fl, fl_note = tp.floor(full, rec.get("structured_floor"))
    if fl is None:
        unknown.append("floor" + (f" ({fl_note})" if fl_note else ""))
    elif fl < config.MIN_FLOOR:
        excluded.append("prízemie" if fl == 0 else f"{fl}. poschodie")

    bal = tp.balcony(full)
    if bal is False:
        excluded.append("no balcony")
    elif bal is None:
        unknown.append("balcony")

    cond = tp.condition(full, rec.get("structured_condition"))
    if cond == "original":
        excluded.append("original condition")
    elif cond is None:
        unknown.append("condition")

    rent = rec.get("rent") or tp.rent_from_text(full)
    # Energies:
    #   nehnutelnosti.sk -> the portal field under the rent ("+ 150 €/mes. energie")
    #                       always wins; only if it is missing, read the text.
    #   bazos.sk         -> text only (the portal has no energy field).
    if rec["source"] == nehnutelnosti.SOURCE and rec.get("structured_energy") is not None:
        en = {"status": "portal", "amount": rec["structured_energy"]}
    else:
        en = tp.energies(full, rent)
    if en["status"] == "unknown":
        flags.append("energies unknown")
    elif en["status"] == "guessed":
        flags.append(f"energies guessed from text ({en['amount']} €)")

    prov = tp.provision(full, rent, rec.get("is_agency"))
    if prov["source"] == "assumed":
        flags.append("provision assumed 1× rent")

    effective = None
    if rent is None:
        unknown.append("rent")
    else:
        energy = en["amount"] or 0
        effective = round(rent + energy + prov["amount"] / config.CONTRACT_MONTHS)
        if en["amount"] is not None and rent + energy < config.MIN_RENT_PLUS_ENERGIES:
            excluded.append(f"suspiciously low ({rent + energy:.0f} € with energies)")
        elif en["amount"] is None and rent < config.MIN_RENT_PLUS_ENERGIES:
            unknown.append("rent below 600 € and energies unknown")
        if effective > config.NEAR_MISS_MAX:
            excluded.append(f"too expensive ({effective} €/month)")

    if excluded:
        status = "excluded"
    elif one_and_half:
        status = "rooms15"   # own section, whatever else is unknown
    elif unknown:
        status = "check"
    elif effective <= config.MAX_EFFECTIVE:
        status = "match"
    else:
        status = "near"

    return {
        "status": status,
        "district": dist,
        "rooms": rooms,
        "floor": fl,
        "balcony": bal,
        "condition": cond,
        "rent": rent,
        "energy_status": en["status"],
        "energy": en["amount"],
        "provision": prov["amount"],
        "provision_source": prov["source"],
        "effective": effective,
        "area": tp.area_m2(full),
        "excluded": excluded,
        "unknown": unknown,
        "flags": flags,
    }
