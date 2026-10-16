from app.events import engine


def pair():
    first = dict(title="Festeggiamenti di S. Angelo", event_city="Porcia", place="Porcia",
                 venue="Via San Cristoforo - fraz. Talponedo", source="TurismoFVG", category="sagra",
                 is_traditional=True, date="4 settembre 2026 - 13 settembre 2026",
                 description="4, 5, 6 e 11, 12, 13 settembre Sei serate per ritrovarsi")
    second = dict(title="Talponedo di Porcia (PN) – Festa di Sant’Angelo", event_city="Porcia",
                  place="Talponedo di Porcia", venue="Talponedo di Porcia", address="Via San Cristoforo",
                  source="SagreFVG", category="sagra", is_traditional=True, date=first["date"])
    return first, second


def test_merges_patron_feast_and_preserves_explicit_days():
    first, second = pair()
    records = engine.dedupe_similar_events([second, first], "Pordenone")
    assert len(records) == 1
    assert records[0]["source"] == "TurismoFVG"
    assert records[0]["occurrences"] == [f"2026-09-{day:02}" for day in [4, 5, 6, 11, 12, 13]]
    assert set(records[0]["alternate_sources"]) == {"TurismoFVG", "SagreFVG"}


def test_same_patron_different_municipality_is_not_merged():
    first, second = pair()
    second.update(event_city="Udine", place="Udine", venue="Centro", address="Piazza Libertà")
    assert not engine.events_are_probable_duplicates(first, second)


def test_dates_inside_narrative_are_not_an_opening_schedule():
    first, _ = pair()
    first["description"] = "Il programma ricorda il 4, 5, 6 settembre"
    assert not engine.with_explicit_event_days(first).get("occurrences")
