from dataclasses import dataclass
from typing import Optional

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.repositories.event_repository import EventRepository
from app.services.ingestion.parser_service import (
    EventFeatures,
    deserialize_event_features,
    event_features_to_text,
    serialize_event_features,
)


HISTORY_COLUMNS = [
    "email",
    "idade",
    "cidade",
    "faculdade",
    "eventos_passados",
    "valor_medio",
    "freq_compra",
    "historical_event_description",
    "historical_event_category",
    "historical_event_price",
    "historical_event_location",
    "historical_event_size",
    "historical_event_vibe",
    "historical_event_audience_type",
    "historical_event_colleges",
    "historical_event_genres",
    "historical_event_themes",
    "historical_event_artists",
    "historical_event_brands",
]


@dataclass
class ClientHistory:
    df: pd.DataFrame
    past_event_descriptions: str
    event_features: list[EventFeatures]
    event_count: int


async def save_upload_history(
    db: AsyncSession,
    client_id: str,
    event_features: EventFeatures,
    df: pd.DataFrame,
    file_name: Optional[str] = None,
) -> tuple[int, int]:
    customer_records = [
        _customer_record_from_row(row)
        for row in df.to_dict(orient="records")
    ]

    repo = EventRepository(db)
    event = await repo.create_with_customer_records(
        client_id=client_id,
        description=serialize_event_features(event_features),
        customer_records=customer_records,
        file_name=file_name,
    )

    return event.id, len(customer_records)


async def load_client_history(
    db: AsyncSession,
    client_id: str,
) -> Optional[ClientHistory]:
    repo = EventRepository(db)
    events = await repo.get_with_customers_by_client(client_id)

    if not events:
        return None

    records = []
    descriptions = []
    event_features = []

    for event in events:
        features = deserialize_event_features(event.description)
        event_features.append(features)
        descriptions.append(event_features_to_text(features))
        for customer in event.customers:
            records.append(_record_from_customer(customer, features))

    df = pd.DataFrame(records, columns=HISTORY_COLUMNS)

    return ClientHistory(
        df=df,
        past_event_descriptions=" ".join(descriptions),
        event_features=event_features,
        event_count=len(events),
    )


def _customer_record_from_row(row: dict) -> dict:
    return {
        "email": str(row["email"]),
        "cidade": _optional_str(row.get("cidade")),
        "faculdade": _optional_str(row.get("faculdade")),
        "idade": _optional_int(row.get("idade")),
        "eventos_passados": _json_list(row.get("eventos_passados")),
        "valor_medio": _optional_float(row.get("valor_medio")),
        "freq_compra": _optional_int(row.get("freq_compra")),
    }


def _record_from_customer(customer: Customer, event_features: EventFeatures) -> dict:
    return {
        "email": customer.email,
        "idade": customer.idade,
        "cidade": customer.cidade,
        "faculdade": customer.faculdade,
        "eventos_passados": customer.eventos_passados or [],
        "valor_medio": customer.valor_medio,
        "freq_compra": customer.freq_compra,
        "historical_event_description": event_features_to_text(event_features),
        "historical_event_category": event_features.category,
        "historical_event_price": event_features.price,
        "historical_event_location": event_features.location,
        "historical_event_size": event_features.size,
        "historical_event_vibe": event_features.vibe,
        "historical_event_audience_type": event_features.audience_type,
        "historical_event_colleges": event_features.colleges,
        "historical_event_genres": event_features.genres,
        "historical_event_themes": event_features.themes,
        "historical_event_artists": event_features.artists,
        "historical_event_brands": event_features.brands,
    }


def _optional_str(value) -> Optional[str]:
    if _is_null(value):
        return None
    return str(value)


def _optional_int(value) -> Optional[int]:
    if _is_null(value):
        return None
    return int(value)


def _optional_float(value) -> Optional[float]:
    if _is_null(value):
        return None
    return float(value)


def _json_list(value) -> list[str]:
    if _is_null(value):
        return []

    if isinstance(value, list):
        return [str(item) for item in value if not _is_null(item)]

    return [str(value)]


def _is_null(value) -> bool:
    if value is None:
        return True

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
