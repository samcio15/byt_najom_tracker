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


# --------------------------------------------------------------------------- #
# Energies: nehnutelnosti portal field first, text only as fallback
# --------------------------------------------------------------------------- #

def test_structured_energy_split_across_elements():
    """JuFlppxoHTX (Astrová): the page shows '+ 150 €/mes. energie' under the
    rent, but the parts are separate HTML elements, so they arrive as separate lines."""
    from tracker.sources.nehnutelnosti import _structured_energy
    assert _structured_energy(["650 €/mes.", "+", "150 €/mes.", "energie", "13,83 €/m²/mes."]) == 150
    assert _structured_energy(["650 €/mes.", "+ 150 €/mes.", "energie"]) == 150
    assert _structured_energy(["650\u00a0€/mes.", "+\u00a0150\u00a0€/mes. energie"]) == 150
    assert _structured_energy(["1 050 €/mes.", "+ 250 € energie"]) == 250
    # An amount further down (description, similar listings) is not the field.
    assert _structured_energy(["650 €/mes.", "13,83 €/m²/mes.", "Popis", "+ 150 € energie"]) is None


def test_parse_detail_reads_split_energy_field():
    from tracker.sources import nehnutelnosti
    html = """<html><body><h1>Prenajmem 2i byt na Astrovej ul.</h1>
      <p>Astrová, Bratislava-Ružinov, okres Bratislava II</p>
      <span>2 izbový byt</span><span>47 m²</span><span>Kompletná rekonštrukcia</span>
      <p><strong>650 €/mes.</strong></p>
      <p><span>+ </span><span>150 €/mes.</span> <span>energie</span></p>
      <p>13,83 €/m²/mes.</p>
      <h3>Popis nehnuteľnosti</h3>
      <p>Byt na 3. poschodí, balkón. Cena: 650€/mesiac (+energie)</p>
      <p>Čítať ďalej</p></body></html>"""
    d = nehnutelnosti.parse_detail(html)
    assert d["structured_energy"] == 150 and d["rent"] == 650


def test_portal_energy_field_beats_text():
    """No more 'vrátane energií overrules the portal field'."""
    from tracker.evaluate import evaluate
    rec = {"source": "nehnutelnosti", "title": "2-izbový byt", "rent": 700,
           "location": "Bratislava-Ružinov", "structured_energy": 150,
           "detail_text": "2-izbový byt, 3. poschodie, balkón, po rekonštrukcii. "
                          "Cena 850 € vrátane energií."}
    e = evaluate(rec)
    assert (e["energy_status"], e["energy"]) == ("portal", 150)


def test_text_used_when_portal_field_missing():
    from tracker.evaluate import evaluate
    rec = {"source": "nehnutelnosti", "title": "2-izbový byt", "rent": 700,
           "location": "Bratislava-Ružinov",
           "detail_text": "3. poschodie, balkón, po rekonštrukcii. Nájom 700 € + 180 € energie."}
    e = evaluate(rec)
    assert (e["energy_status"], e["energy"]) == ("separate", 180)


def test_bazos_uses_text_only():
    from tracker.evaluate import evaluate
    rec = {"source": "bazos", "title": "Prenájom 2-izbový byt Ružinov", "rent": 700,
           "postcode": "82101", "structured_energy": 999,  # must be ignored
           "detail_text": "3. poschodie, balkón, po rekonštrukcii. Nájom 700 € + 160 € energie."}
    e = evaluate(rec)
    assert (e["energy_status"], e["energy"]) == ("separate", 160)
