from app.models.customer import Customer
from app.models.event import Event
from app.services.analytics.coattendance_service import compute_coattendance_metrics


def make_event(event_id: int, emails: list[str]) -> Event:
    event = Event(id=event_id)
    event.customers = [Customer(email=email) for email in emails]
    return event


def test_compute_coattendance_metrics():
    events = [
        make_event(1, ["a@example.com", "b@example.com", "c@example.com"]),
        make_event(2, ["a@example.com", "b@example.com"]),
        make_event(3, ["a@example.com", "d@example.com"]),
    ]

    result = compute_coattendance_metrics(events, top_n=10, min_shared_events=1, top_partners=3)

    assert result["total_events"] == 3
    assert result["total_customers"] == 4
    assert result["total_edges"] == 4
    assert len(result["top_customers"]) == 4

    first = result["top_customers"][0]
    assert first["email"] == "a@example.com"
    assert first["degree"] == 3
    assert first["weighted_degree"] == 4
    assert first["events_count"] == 3
    assert len(first["top_partners"]) == 3

    second = result["top_customers"][1]
    assert second["email"] == "b@example.com"
    assert second["degree"] == 2
    assert second["weighted_degree"] == 3
