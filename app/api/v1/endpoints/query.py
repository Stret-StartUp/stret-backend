from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.event_repository import EventRepository
from app.services.analytics.customer_ranking_service import rank_customers_for_event
from app.services.ingestion.parser_service import build_event_features, has_event_scope
from app.utils.file_handler import generate_excel

router = APIRouter()


@router.post("/query")
async def query_data(
    client_id: str = Form(...),
    event_description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    location: Optional[str] = Form(None),
    size: Optional[str] = Form(None),
    vibe: Optional[str] = Form(None),
    audience_type: Optional[str] = Form(None),
    colleges: Optional[str] = Form(None),
    genres: Optional[str] = Form(None),
    themes: Optional[str] = Form(None),
    artists: Optional[str] = Form(None),
    brands: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    historical_events = await EventRepository(db).get_with_customers_by_client(client_id)

    if not historical_events:
        return {"error": "Nenhum dado encontrado para esse cliente"}

    current_event_features = build_event_features(
        description=event_description,
        category=category,
        price=price,
        location=location,
        size=size,
        vibe=vibe,
        audience_type=audience_type,
        colleges=colleges,
        genres=genres,
        themes=themes,
        artists=artists,
        brands=brands,
    )

    if not has_event_scope(current_event_features):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Informe ao menos uma caracteristica do evento alvo "
                "(category, price, location, size, vibe, audience_type, colleges, "
                "genres, themes, artists, brands ou event_description)."
            ),
        )

    result = rank_customers_for_event(
        target=current_event_features,
        historical_events=historical_events,
        top_n=100,
    )

    if result.ranked_customers.empty:
        return {"error": "Nenhum cliente encontrado nos eventos historicos desse cliente"}

    return generate_excel(result.ranked_customers)
