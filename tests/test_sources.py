"""Parser tests against pages saved from the real sites (Sep 2026).
If a site changes its layout, these still pass but live runs will dump
the new page into data/debug/ — save it here as a new fixture and fix the parser."""
from pathlib import Path

from tracker.sources import bazos, nehnutelnosti

F = Path(__file__).parent / "fixtures"


def read(name):
    return (F / name).read_text(encoding="utf-8")


def test_nehnutelnosti_list():
    cards = nehnutelnosti.parse_list(read("nehn_list.html"))
    assert len(cards) == 30
    c = next(c for c in cards if "JunEjsigkpx" in c["id"])
    assert c["rent"] == 800
    assert nehnutelnosti.district_of(c) == "Ružinov"
    assert all("developersky-projekt" not in c["url"] for c in cards)
    assert nehnutelnosti.last_page(read("nehn_list.html")) == 24


def test_nehnutelnosti_detail():
    d = nehnutelnosti.parse_detail(read("nehn_detail.html"))
    assert "250€ energie" in d["detail_text"]
    assert d["structured_condition"] == "Kompletná rekonštrukcia"
    assert d["is_agency"] is True
    assert d["rent"] == 800


def test_bazos_list():
    cards = bazos.parse_list(read("bazos_list.html"))
    assert len(cards) == 20
    c = next(c for c in cards if c["id"] == "bazos:195892150")
    assert c["rent"] == 650 and c["postcode"] == "08005"
    assert c["portal_date"] == "2026-09-29"


def test_bazos_detail():
    d = bazos.parse_detail(read("bazos_detail.html"))
    assert "vrátané energií" in d["detail_text"]
    assert d["postcode"] == "08005" and d["rent"] == 650


def test_nehnutelnosti_structured_energy_line():
    from tracker.sources.nehnutelnosti import _structured_energy
    assert _structured_energy(["700 €/mes.", "+ 200 €/mes. energie", "13,46 €/m²/mes."]) == 200
    assert _structured_energy(["800 €/mes.", "14,81 €/m²/mes."]) is None


def test_evaluate_uses_portal_energy_field_and_reserved():
    from tracker.evaluate import evaluate
    base = {"source": "nehnutelnosti", "location": "Bosákova 7, Bratislava-Petržalka",
            "rent": 700, "structured_condition": "Novostavba", "is_agency": False,
            "detail_text": "2-izbový byt s balkónom na 13. poschodí. 700 € / mesiac + služby"}
    e = evaluate({**base, "title": "Príjemný 2-izbový byt", "structured_energy": 200})
    assert (e["energy"], e["effective"], e["status"]) == (200, 900, "excluded")
    e = evaluate({**base, "title": "Rezervované 2-izbový byt", "structured_energy": 50})
    assert "reserved or no longer available" in e["excluded"]
