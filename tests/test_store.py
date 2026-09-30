from tracker import store


def rec(id_, rent, source="bazos", text="x" * 200):
    return {"id": id_, "source": source, "title": "t", "url": "u", "detail_text": text,
            "fp": store.fingerprint(text), "eval": {"rent": rent, "district": "Ružinov", "area": 50}}


def test_history_removal_and_repost():
    s = {"listings": {}, "runs": [], "notified": []}
    store.upsert(s, rec("bazos:1", 800), "2026-09-01")
    store.upsert(s, rec("bazos:1", 780), "2026-09-02")
    assert s["listings"]["bazos:1"]["price_history"] == [["2026-09-01", 800], ["2026-09-02", 780]]

    store.mark_missing(s, "bazos", set(), "2026-09-03")
    assert s["listings"]["bazos:1"]["active"]           # one miss is tolerated
    store.mark_missing(s, "bazos", set(), "2026-09-04")
    assert not s["listings"]["bazos:1"]["active"]

    # Same text under a new id = repost; keeps the original first-seen date.
    store.upsert(s, rec("bazos:2", 780), "2026-09-10")
    assert s["listings"]["bazos:2"]["group"] == "bazos:1"
    assert store.group_first_seen(s, "bazos:1") == "2026-09-01"


def test_cross_site_duplicate_by_area_and_rent():
    s = {"listings": {}, "runs": [], "notified": []}
    store.upsert(s, rec("nehnutelnosti:a", 750, "nehnutelnosti", "a" * 200), "2026-09-01")
    store.upsert(s, rec("bazos:9", 750, "bazos", "b" * 200), "2026-09-05")
    assert s["listings"]["bazos:9"]["group"] == "nehnutelnosti:a"
