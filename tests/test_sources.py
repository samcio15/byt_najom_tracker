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
