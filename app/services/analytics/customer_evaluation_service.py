"""
Service responsável por avaliar/categorizar clientes com base em eventos similares.

Responsabilidades:
- Filtrar clientes que aparecem em eventos similares
- Categorizar clientes por quão similares foram seus eventos
- Dar maior peso a clientes em eventos muito similares
- Agregar informações de múltiplos eventos
- Aplicar scoring ponderado via IntelligentWeightingService (única fonte de pesos)
"""

from dataclasses import dataclass

import pandas as pd

from app.services.analytics.event_similarity_service import SimilarEvent
from app.services.analytics.feature_builder import FEATURE_COLUMNS, build_customer_features
from app.services.analytics.intelligent_weighting import IntelligentWeightingService
from app.services.ingestion.parser_service import EventFeatures


@dataclass
class CustomerCategory:
    """Categoria de cliente baseada em eventos similares."""

    HIGH = "high"      # Score de evento >= 0.7
    MEDIUM = "medium"  # Score de evento 0.4 a 0.7
    LOW = "low"        # Score de evento < 0.4


@dataclass
class CustomerEvaluationResult:
    """Resultado da avaliação de clientes."""

    all_customers: pd.DataFrame
    high_category: pd.DataFrame
    medium_category: pd.DataFrame
    low_category: pd.DataFrame


def evaluate_customers_from_similar_events(
    similar_events: list[SimilarEvent],
    target: EventFeatures,
    min_event_similarity: float = 0.0,
    use_learned_weights: bool = True,
) -> CustomerEvaluationResult:
    """
    Avalia clientes com base em eventos similares.

    Fluxo de scoring:
    1. build_customer_features → calcula scores BRUTOS (0–1), sem pesos
    2. _apply_learned_weights  → aplica pesos via IntelligentWeightingService

    Não há double-weighting: os pesos do settings não são usados no feature_builder.
    """
    all_records = []

    for similar_event in similar_events:
        if similar_event.similarity_score < min_event_similarity:
            continue

        category = _get_similarity_category(similar_event.similarity_score)

        for customer in similar_event.event.customers or []:
            if not customer.email:
                continue

            all_records.append(
                {
                    "email": customer.email,
                    "email_normalized": str(customer.email).strip().lower(),
                    "idade": customer.idade,
                    "cidade": customer.cidade,
                    "faculdade": customer.faculdade,
                    "valor_medio": customer.valor_medio,
                    "freq_compra": customer.freq_compra,
                    "eventos_passados": customer.eventos_passados or [],
                    # Campos de similaridade de evento
                    "weighted_event_similarity": similar_event.similarity_score,
                    "max_event_similarity": similar_event.similarity_score,
                    "avg_event_similarity": similar_event.similarity_score,
                    # Campos históricos do evento de origem
                    "historical_event_description": getattr(similar_event.event, "description", None),
                    "historical_event_category": getattr(similar_event.event, "category", None),
                    "historical_event_location": getattr(similar_event.event, "location", None),
                    "historical_event_size": getattr(similar_event.event, "size", None),
                    "historical_event_vibe": getattr(similar_event.event, "vibe", None),
                    "historical_event_audience_type": getattr(similar_event.event, "audience_type", None),
                    "historical_event_colleges": getattr(similar_event.event, "colleges", []),
                    "historical_event_genres": getattr(similar_event.event, "genres", []),
                    "historical_event_themes": getattr(similar_event.event, "themes", []),
                    "historical_event_artists": getattr(similar_event.event, "artists", []),
                    "historical_event_brands": getattr(similar_event.event, "brands", []),
                    # Metadados
                    "event_id": similar_event.event_id,
                    "event_similarity_score": similar_event.similarity_score,
                    "event_category": category,
                    "event_breakdown": similar_event.breakdown.to_dict(),
                }
            )

    if not all_records:
        empty_df = pd.DataFrame()
        return CustomerEvaluationResult(
            all_customers=empty_df,
            high_category=empty_df,
            medium_category=empty_df,
            low_category=empty_df,
        )

    all_df = pd.DataFrame(all_records)

    # ETAPA 1: scores brutos — feature_builder NÃO aplica pesos
    all_df = build_customer_features(all_df, target)

    # ETAPA 2: ponderação — única fonte de pesos é o IntelligentWeightingService
    if use_learned_weights:
        all_df = _apply_learned_weights(all_df)

    # Separar por categoria
    high_df = all_df[all_df["event_similarity_score"] >= 0.7].copy()
    medium_df = all_df[
        (all_df["event_similarity_score"] >= 0.4) & (all_df["event_similarity_score"] < 0.7)
    ].copy()
    low_df = all_df[all_df["event_similarity_score"] < 0.4].copy()

    return CustomerEvaluationResult(
        all_customers=all_df,
        high_category=high_df,
        medium_category=medium_df,
        low_category=low_df,
    )


def _apply_learned_weights(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula score final usando IntelligentWeightingService.

    Recebe features brutas (0–1) do feature_builder e aplica os pesos
    aprendidos. É a ÚNICA etapa que pondera — não há multiplicação prévia
    pelos pesos do settings.
    """
    weighting = IntelligentWeightingService()

    feature_cols = [
        "event_similarity_score",
        "affinity_score",
        "ticket_score",
        "age_score",
        "purchase_timing_score",
        "vibe_score",
        "frequency_score",
    ]

    missing = [col for col in feature_cols if col not in df.columns]
    if missing:
        # Fallback silencioso: mantém score placeholder do build_customer_features
        return df

    records = df[feature_cols].to_dict(orient="records")
    df = df.copy()
    df["score"] = weighting.batch_score(records)

    return df


def _get_similarity_category(score: float) -> str:
    """Categoriza um score de similaridade de evento."""
    if score >= 0.7:
        return CustomerCategory.HIGH
    elif score >= 0.4:
        return CustomerCategory.MEDIUM
    else:
        return CustomerCategory.LOW
