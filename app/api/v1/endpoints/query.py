from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.analytics.scoring_service import score_clients
from app.services.ingestion.database_storage_service import load_client_history
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
    history = await load_client_history(db, client_id)

    if history is None or history.df.empty:
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

    df_scored = score_clients(
        history.df,
        history.event_features,
        current_event_features
    )

    df_filtered = df_scored.head(100)

    return generate_excel(df_filtered)
