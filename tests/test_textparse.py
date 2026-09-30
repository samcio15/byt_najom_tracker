import pytest

from tracker import textparse as tp


@pytest.mark.parametrize("title,text,expected", [
    ("Prenájom 2izbovy byt Presov", "", 2),
    ("Dvojizbový byt Petržalka", "", 2),
    ("2-izb. byt s loggiou", "", 2),
    ("Byt 2+kk Ružinov", "", 2),
    ("Garsónka Ružinov", "", 1),
    ("1,5-izbový byt", "", 1.5),
    ("3-izbový byt, 2 izby orientované na juh", "", 3),
    ("Prenájom bytu", "Ponúkam 2 izbový byt", 2),
    ("Prenájom bytu", "", None),
])
def test_rooms(title, text, expected):
    assert tp.rooms(title, text) == expected


@pytest.mark.parametrize("text,expected", [
    ("Byt sa nachádza na 3. poschodí a jeho súčasťou je balkón", 3),
    ("3. poschodie / bez výťahu", 3),
    ("byt na prízemí", 0),
    ("zvýšené prízemie", 0),
    ("byt je na 1. poschodí", 1),
    ("na prvom poschodí", 1),
    ("na treťom poschodí 8-poschodového domu", 3),
    ("poschodie: 5/8", 5),
    ("byt na 4.NP", 3),
    ("byt v 8 poschodovom dome", None),
    ("nachádza sa na 5. podlaží", 4),
    ("nachádza sa na 1. podlaží", 1),
    ("bez informácie", None),
])
def test_floor(text, expected):
    assert tp.floor(text)[0] == expected


def test_floor_ambiguous_podlazie():
    val, note = tp.floor("byt na 2. podlaží")
    assert val is None and "ambiguous" in note


@pytest.mark.parametrize("text,expected", [
    ("súčasťou je balkón", True),
    ("priestranná lodžia", True),
    ("byt s loggiou", True),
    ("byt bez balkóna", False),
    ("francúzsky balkón v spálni", None),
    ("francúzsky balkón a veľká lodžia", True),
    ("pekný byt", None),
])
def test_balcony(text, expected):
    assert tp.balcony(text) == expected


@pytest.mark.parametrize("text,structured,expected", [
    ("", "Kompletná rekonštrukcia", "renovated"),
    ("", "Čiastočná rekonštrukcia", "partial"),
    ("byt prešiel kompletnou rekonštrukciou", None, "renovated"),
    ("byt po rekonštrukcii", None, "renovated"),
    ("zrekonštruovaný byt", None, "renovated"),
    ("čiastočne zrekonštruovaný", None, "partial"),
    ("byt v pôvodnom stave", None, "original"),
    ("pôvodný stav, kúpeľňa po rekonštrukcii", None, "partial"),
    ("byt v novostavbe", None, "new"),
    ("pekný byt", None, None),
])
def test_condition(text, structured, expected):
    assert tp.condition(text, structured) == expected


@pytest.mark.parametrize("text,status,amount", [
    ("800€ / mesiac + 250€ energie", "separate", 250),
    ("Nájomné je 650€ mesačne,vrátané energií aj internetu.", "included", 0),
    ("cena 700 € + energie cca 150 €", "separate", 150),
    ("nájom 700 €, energie 120 - 160 € mesačne", "separate", 160),
    ("zálohy na energie 180 EUR", "separate", 180),
    ("nájom 650,- € + 200,- € zálohy", "separate", 200),
    ("cena je vrátane všetkých energií", "included", 0),
    ("nájom 750 € + energie", "unknown", None),
    ("pekný byt", "unknown", None),
    ("850 € vrátane energií (+ 150 € energie)", "ambiguous", 150),
])
def test_energies(text, status, amount):
    e = tp.energies(text)
    assert (e["status"], e["amount"]) == (status, amount)


@pytest.mark.parametrize("text,rent,agency,amount,source", [
    ("plus provízia realitnej kancelárie", 800, True, 800, "assumed"),
    ("provízia RK 500 €", 700, None, 500, "stated"),
    ("provízia vo výške jedného mesačného nájmu", 700, None, 700, "stated"),
    ("provízia 50 % z mesačného nájmu", 700, None, 350, "stated"),
    ("prenájom priamo od majiteľa, RK nevolať", 700, None, 0, "none"),
    ("bez provízie", 700, True, 0, "none"),
    ("provízia RK, depozit 800 €", 700, None, 700, "assumed"),
    ("pekný byt", 700, False, 0, "private"),
])
def test_provision(text, rent, agency, amount, source):
    p = tp.provision(text, rent, agency)
    assert (p["amount"], p["source"]) == (amount, source)


@pytest.mark.parametrize("text,expected", [
    ("Drieňová ulica, Bratislava-Ružinov", "Ružinov"),
    ("byt v Petržalke", "Petržalka"),
    ("Karlova Ves, Dlhé diely", "Karlova Ves"),
    ("v Karlovej Vsi", "Karlova Ves"),
    ("Bratislava - Nové Mesto, Kramáre", "Nové Mesto"),
    ("Nové Mesto nad Váhom", None),
    ("byt v Rači", "Rača"),
    ("Staré Mesto", None),
    ("novej mestskej časti", None),
])
def test_district(text, expected):
    assert tp.district_from_text(text) == expected


def test_postcode():
    assert tp.district_from_postcode("851 04") == "Petržalka"
    assert tp.district_from_postcode("821 07") is None


def test_wanted_ad():
    assert not tp.is_wanted_ad("Hľadám 2-izbový byt")
    assert tp.is_wanted_ad("Prenájom 2-izbový byt")


# Regression cases taken from real nehnutelnosti.sk listings (Sep 2026).
@pytest.mark.parametrize("text,rent,status,amount", [
    ("Cena za nájom je 750 € mesačne plus 200 € energie vrátane internetu plus 50 € garážové státie.",
     750, "separate", 200),
    ("K cene sa pripočítavajú energie 250 €/1 osoba (v cene sú zahrnuté energie vrátane KTV), 300 €/2 osoby.",
     800, "separate", 250),
    ("Cena prenájmu: 750 €/mesiac + 350 € energie vrátane parkovacieho státia.", 750, "separate", 350),
    ("Nájomné: 710 € / mesiac Energie: 190 € / mesiac Celková mesačná platba: 900 €", 710, "separate", 190),
    ("Cena: 900€ / mesiac (vrátane energií) (nájom 580 € + 320 € energie)", 580, "ambiguous", 320),
    ("Nájom 850 € vrátane energií, energie tvoria cca 150 €.", 850, "included", 0),
])
def test_energies_real(text, rent, status, amount):
    e = tp.energies(text, rent)
    assert (e["status"], e["amount"]) == (status, amount)


@pytest.mark.parametrize("text,rent,amount,source", [
    ("Provízia sa neplatí.", 800, 0, "none"),
    ("provízia realitnej kancelárii vo výške 1-mesačného nájmu", 750, 750, "stated"),
    ("provízia realitnej kancelárie je 500 €.", 750, 500, "stated"),
])
def test_provision_real(text, rent, amount, source):
    p = tp.provision(text, rent, True)
    assert (p["amount"], p["source"]) == (amount, source)
