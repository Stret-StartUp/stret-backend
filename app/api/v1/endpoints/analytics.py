from fastapi import APIRouter, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.event_repository import EventRepository
from app.services.analytics.coattendance_service import compute_coattendance_metrics

router = APIRouter()


@router.post("/analytics/most-connected")
async def most_connected_customers(
    client_id: str = Form(...),
    top_n: int = Form(50),
    min_shared_events: int = Form(1),
    top_partners: int = Form(5),
    db: AsyncSession = Depends(get_db),
):
    events = await EventRepository(db).get_with_customers_by_client(client_id)

    if not events:
        return {"error": "Nenhum dado encontrado para esse cliente"}

    metrics = compute_coattendance_metrics(
        events=events,
        top_n=top_n,
        min_shared_events=min_shared_events,
        top_partners=top_partners,
    )

    return {
        "client_id": client_id,
        **metrics,
    }
