from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from app.models.event import Event


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def build_customer_event_map(events: list[Event]) -> dict[str, set[int]]:
    customer_events: dict[str, set[int]] = {}

    for event in events:
        event_emails = {
            _normalize_email(customer.email)
            for customer in getattr(event, "customers", [])
            if getattr(customer, "email", None)
        }
        for email in event_emails:
            customer_events.setdefault(email, set()).add(event.id)

    return customer_events


def build_coattendance_graph(events: list[Event]) -> dict[str, dict[str, int]]:
    graph: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for event in events:
        event_emails = sorted(
            {
                _normalize_email(customer.email)
                for customer in getattr(event, "customers", [])
                if getattr(customer, "email", None)
            }
        )

        for index, email in enumerate(event_emails):
            for partner in event_emails[index + 1 :]:
                graph[email][partner] += 1
                graph[partner][email] += 1

    # Convert default dicts to normal dicts for JSON-friendly output
    return {email: dict(neighbors) for email, neighbors in graph.items()}


def _filter_neighbors(
    neighbors: dict[str, int],
    min_shared_events: int,
) -> dict[str, int]:
    return {
        partner: weight
        for partner, weight in neighbors.items()
        if weight >= min_shared_events
    }


def _build_top_partners(
    neighbors: dict[str, int],
    top_partners: int,
) -> list[dict[str, int]]:
    sorted_partners = sorted(
        neighbors.items(),
        key=lambda item: (-item[1], item[0]),
    )
    return [
        {"email": partner, "shared_events": weight}
        for partner, weight in sorted_partners[:top_partners]
    ]


def compute_coattendance_metrics(
    events: list[Event],
    top_n: int = 50,
    min_shared_events: int = 1,
    top_partners: int = 5,
) -> dict[str, object]:
    customer_events = build_customer_event_map(events)
    graph = build_coattendance_graph(events)

    summaries: list[dict[str, object]] = []

    for email, neighbors in graph.items():
        shared_neighbors = _filter_neighbors(neighbors, min_shared_events)
        if not shared_neighbors:
            continue

        summaries.append(
            {
                "email": email,
                "events_count": len(customer_events.get(email, [])),
                "degree": len(shared_neighbors),
                "weighted_degree": sum(shared_neighbors.values()),
                "top_partners": _build_top_partners(shared_neighbors, top_partners),
            }
        )

    summaries.sort(
        key=lambda entry: (
            -entry["weighted_degree"],
            -entry["degree"],
            -entry["events_count"],
            entry["email"],
        )
    )

    visible_customers = len(summaries)
    unique_edges = 0
    seen_pairs: set[tuple[str, str]] = set()

    for email, neighbors in graph.items():
        for partner, weight in neighbors.items():
            if weight < min_shared_events:
                continue
            pair = tuple(sorted((email, partner)))
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                unique_edges += 1

    return {
        "total_events": len(events),
        "total_customers": len(customer_events),
        "total_edges": unique_edges,
        "top_customers": summaries[:top_n],
        "visible_customers": visible_customers,
    }
