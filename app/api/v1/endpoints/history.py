from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.event_repository import EventRepository
from app.services.ingestion.parser_service import (
    deserialize_event_features,
    event_features_to_text,
)

router = APIRouter()


@router.get("/history")
async def list_history(
    client_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    repo = EventRepository(db)
    events = await repo.get_with_customers_by_client(client_id)

    return {
        "client_id": client_id,
        "total_events": len(events),
        "events": [
            _event_payload(event)
            for event in sorted(events, key=lambda item: item.created_at, reverse=True)
        ],
    }


def _event_payload(event):
    features = deserialize_event_features(event.description)
    customers = event.customers or []

    return {
        "id": event.id,
        "file_name": event.file_name,
        "created_at": event.created_at,
        "customers_count": len(customers),
        "avg_age": _average([customer.idade for customer in customers]),
        "avg_ticket": _average([customer.valor_medio for customer in customers]),
        "summary": event_features_to_text(features),
        "features": asdict(features),
    }


def _average(values):
    clean_values = [value for value in values if value is not None]
    if not clean_values:
        return None

    return round(sum(clean_values) / len(clean_values), 2)
