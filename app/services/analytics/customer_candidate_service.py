from collections import defaultdict
from typing import Iterable, Optional

import pandas as pd

from app.models.customer import Customer
from app.services.analytics.event_similarity_service import SimilarEvent
from app.services.ingestion.parser_service import event_features_to_text


def build_customer_candidates(
    similar_events: list[SimilarEvent],
    min_event_similarity: float = 0.0,
) -> pd.DataFrame:
    records_by_email: dict[str, list[dict]] = defaultdict(list)

    for similar_event in similar_events:
        if similar_event.similarity_score < min_event_similarity:
            continue

        for customer in similar_event.event.customers or []:
            if not customer.email:
                continue

            email = _normalize_email(customer.email)
            records_by_email[email].append(_customer_event_record(customer, similar_event))

    records = [
        _aggregate_customer_records(email, records)
        for email, records in records_by_email.items()
    ]

    return pd.DataFrame(records)


def _customer_event_record(customer: Customer, similar_event: SimilarEvent) -> dict:
    features = similar_event.features

    return {
        "email": customer.email,
        "email_normalized": _normalize_email(customer.email),
        "idade": customer.idade,
        "cidade": customer.cidade,
        "faculdade": customer.faculdade,
        "eventos_passados": customer.eventos_passados or [],
        "valor_medio": customer.valor_medio,
        "freq_compra": customer.freq_compra,
        "history_event_ids": [similar_event.event_id],
        "history_event_count": 1,
        "history_event_similarity_scores": [similar_event.similarity_score],
        "max_event_similarity": similar_event.similarity_score,
        "avg_event_similarity": similar_event.similarity_score,
        "weighted_event_similarity": similar_event.similarity_score,
        "historical_event_description": [event_features_to_text(features)],
        "historical_event_category": [features.category],
        "historical_event_price": [features.price],
        "historical_event_location": [features.location],
        "historical_event_size": [features.size],
        "historical_event_vibe": [features.vibe],
        "historical_event_audience_type": [features.audience_type],
        "historical_event_colleges": features.colleges,
        "historical_event_genres": features.genres,
        "historical_event_themes": features.themes,
        "historical_event_artists": features.artists,
        "historical_event_brands": features.brands,
    }


def _aggregate_customer_records(email: str, records: list[dict]) -> dict:
    similarity_scores = _flatten(record.get("history_event_similarity_scores") for record in records)
    freq_values = [record.get("freq_compra") or 1 for record in records]

    return {
        "email": _first_non_empty(record.get("email") for record in records),
        "email_normalized": email,
        "idade": _first_non_empty(record.get("idade") for record in records),
        "cidade": _most_common_text(record.get("cidade") for record in records),
        "faculdade": _most_common_text(record.get("faculdade") for record in records),
        "eventos_passados": _flatten(record.get("eventos_passados") for record in records),
        "valor_medio": _mean(record.get("valor_medio") for record in records),
        "freq_compra": _sum(record.get("freq_compra") for record in records),
        "history_event_ids": _flatten(record.get("history_event_ids") for record in records),
        "history_event_count": len(records),
        "history_event_similarity_scores": similarity_scores,
        "max_event_similarity": max(similarity_scores) if similarity_scores else 0.0,
        "avg_event_similarity": _mean(similarity_scores) or 0.0,
        "weighted_event_similarity": _weighted_mean(similarity_scores, freq_values),
        "historical_event_description": " ".join(
            _flatten(record.get("historical_event_description") for record in records)
        ),
        "historical_event_category": " ".join(
            _flatten(record.get("historical_event_category") for record in records)
        ),
        "historical_event_price": _mean(
            _flatten(record.get("historical_event_price") for record in records)
        ),
        "historical_event_location": " ".join(
            _flatten(record.get("historical_event_location") for record in records)
        ),
        "historical_event_size": " ".join(
            _flatten(record.get("historical_event_size") for record in records)
        ),
        "historical_event_vibe": " ".join(
            _flatten(record.get("historical_event_vibe") for record in records)
        ),
        "historical_event_audience_type": " ".join(
            _flatten(record.get("historical_event_audience_type") for record in records)
        ),
        "historical_event_colleges": _flatten(
            record.get("historical_event_colleges") for record in records
        ),
        "historical_event_genres": _flatten(
            record.get("historical_event_genres") for record in records
        ),
        "historical_event_themes": _flatten(
            record.get("historical_event_themes") for record in records
        ),
        "historical_event_artists": _flatten(
            record.get("historical_event_artists") for record in records
        ),
        "historical_event_brands": _flatten(
            record.get("historical_event_brands") for record in records
        ),
    }


def _normalize_email(email: str) -> str:
    return str(email).strip().lower()


def _first_non_empty(values: Iterable) -> Optional[object]:
    for value in values:
        if not _is_empty(value):
            return value
    return None


def _most_common_text(values: Iterable) -> Optional[str]:
    counts = defaultdict(int)

    for value in values:
        if _is_empty(value):
            continue
        counts[str(value)] += 1

    if not counts:
        return None

    return max(counts.items(), key=lambda item: item[1])[0]


def _flatten(values: Iterable) -> list:
    flattened = []

    for value in values:
        if _is_empty(value):
            continue
        if isinstance(value, list):
            flattened.extend(item for item in value if not _is_empty(item))
        elif isinstance(value, tuple):
            flattened.extend(item for item in value if not _is_empty(item))
        else:
            flattened.append(value)

    return flattened


def _mean(values: Iterable) -> Optional[float]:
    valid_values = [float(value) for value in values if not _is_empty(value)]
    if not valid_values:
        return None
    return sum(valid_values) / len(valid_values)


def _sum(values: Iterable) -> Optional[int]:
    valid_values = [int(value) for value in values if not _is_empty(value)]
    if not valid_values:
        return None
    return sum(valid_values)


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    if not values:
        return 0.0

    padded_weights = weights[:len(values)]
    if len(padded_weights) < len(values):
        padded_weights.extend([1.0] * (len(values) - len(padded_weights)))

    total_weight = sum(float(weight) for weight in padded_weights if not _is_empty(weight))
    if total_weight <= 0:
        return _mean(values) or 0.0

    return sum(float(value) * float(weight) for value, weight in zip(values, padded_weights)) / total_weight


def _is_empty(value) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
