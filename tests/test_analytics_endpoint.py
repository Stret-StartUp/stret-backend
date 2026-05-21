from fastapi.testclient import TestClient

from app.main import app
from app.models.customer import Customer
from app.models.event import Event
import app.api.v1.endpoints.analytics as analytics_module


class DummyEventRepository:
    def __init__(self, db):
        self.db = db

    async def get_with_customers_by_client(self, client_id: str):
        event1 = Event(id=1)
        event1.customers = [
            Customer(email="a@example.com"),
            Customer(email="b@example.com"),
        ]
        event2 = Event(id=2)
        event2.customers = [
            Customer(email="a@example.com"),
            Customer(email="c@example.com"),
        ]
        return [event1, event2]


def test_most_connected_endpoint(monkeypatch):
    monkeypatch.setattr(analytics_module, "EventRepository", DummyEventRepository)
    client = TestClient(app)

    response = client.post(
        "/api/v1/analytics/most-connected",
        data={"client_id": "test-client", "top_n": 10, "min_shared_events": 1, "top_partners": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["client_id"] == "test-client"
    assert payload["total_events"] == 2
    assert payload["total_customers"] == 3
    assert payload["total_edges"] == 2
    assert payload["top_customers"][0]["email"] == "a@example.com"
    assert payload["top_customers"][0]["weighted_degree"] == 2
