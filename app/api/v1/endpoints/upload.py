from io import BytesIO
from time import perf_counter
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db.session import get_db
from app.services.ingestion.database_storage_service import save_upload_history
from app.services.ingestion.parser_service import build_event_features, has_event_scope
from app.services.ingestion.transform_service import transform_data
from app.services.ingestion.validation_service import validate_upload
from app.utils.logger import logger

router = APIRouter()


@router.post("/upload")
async def upload_data(
    file: UploadFile = File(...),
    client_id: str = Form(...),
    past_event_description: Optional[str] = Form(None),
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
    started_at = perf_counter()

    content = await validate_upload(file)
    validated_at = perf_counter()
    size_mb = len(content) / (1024 * 1024)
    logger.info(
        "Upload recebido: file=%s size_mb=%.2f client_id=%s",
        file.filename,
        size_mb,
        client_id,
    )

    event_features = build_event_features(
        description=event_description or past_event_description,
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

    if not has_event_scope(event_features):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Informe ao menos uma caracteristica do evento historico "
                "(category, vibe, genres, themes, artists, brands ou event_description)."
            ),
        )

    try:
        raw_df = await run_in_threadpool(pd.read_excel, BytesIO(content))
        read_at = perf_counter()
        logger.info(
            "Excel lido: file=%s raw_rows=%s read_excel_s=%.2f",
            file.filename,
            len(raw_df),
            read_at - validated_at,
        )

        df = await run_in_threadpool(transform_data, raw_df)
        transformed_at = perf_counter()
        logger.info(
            "Excel transformado: file=%s customers=%s transform_s=%.2f",
            file.filename,
            len(df),
            transformed_at - read_at,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    event_id, customers_saved = await save_upload_history(
        db=db,
        client_id=client_id,
        event_features=event_features,
        df=df,
        file_name=file.filename,
    )
    saved_at = perf_counter()
    logger.info(
        "Historico salvo no banco: file=%s event_id=%s customers=%s db_save_s=%.2f",
        file.filename,
        event_id,
        customers_saved,
        saved_at - transformed_at,
    )

    logger.info(
        (
            "Upload processado: file=%s raw_rows=%s customers=%s "
            "validate_s=%.2f read_excel_s=%.2f transform_s=%.2f db_save_s=%.2f total_s=%.2f"
        ),
        file.filename,
        len(raw_df),
        customers_saved,
        validated_at - started_at,
        read_at - validated_at,
        transformed_at - read_at,
        saved_at - transformed_at,
        saved_at - started_at,
    )

    return {
        "message": "Dados armazenados com sucesso",
        "event_id": event_id,
        "customers_saved": customers_saved,
        "processing_time_seconds": round(saved_at - started_at, 2),
    }
