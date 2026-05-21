"""
Service responsável por avaliar/categorizar clientes com base em eventos similares.

Responsabilidades:
- Filtrar clientes que aparecem em eventos similares
- Categorizar clientes por quão similares foram seus eventos
- Dar maior peso a clientes em eventos muito similares
- Agregar informações de múltiplos eventos
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from app.services.analytics.event_similarity_service import SimilarEvent


@dataclass
class CustomerCategory:
    """Categoria de cliente baseada em eventos similares."""

    HIGH = "high"  # Score de evento >= 0.7
    MEDIUM = "medium"  # Score de evento 0.4 a 0.7
    LOW = "low"  # Score de evento < 0.4


@dataclass
class CustomerEvaluationResult:
    """Resultado da avaliação de clientes."""

    all_customers: pd.DataFrame
    high_category: pd.DataFrame  # Eventos com score >= 0.7
    medium_category: pd.DataFrame  # Eventos com score 0.4-0.7
    low_category: pd.DataFrame  # Eventos com score < 0.4


def evaluate_customers_from_similar_events(
    similar_events: list[SimilarEvent],
    min_event_similarity: float = 0.0,
) -> CustomerEvaluationResult:
    """
    Avalia clientes com base em eventos similares.

    Prioriza clientes que aparecem em eventos muito similares ao target.

    Args:
        similar_events: Eventos já ranqueados por similaridade
        min_event_similarity: Score mínimo para incluir evento (0.0 a 1.0)

    Returns:
        CustomerEvaluationResult com clientes categorizados por relevância
    """
    # Coletar todos os registros de clientes com suas categorias
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

    # Separar por categoria
    high_df = all_df[all_df["event_similarity_score"] >= 0.7].copy()
    medium_df = all_df[(all_df["event_similarity_score"] >= 0.4) & (all_df["event_similarity_score"] < 0.7)].copy()
    low_df = all_df[all_df["event_similarity_score"] < 0.4].copy()

    return CustomerEvaluationResult(
        all_customers=all_df,
        high_category=high_df,
        medium_category=medium_df,
        low_category=low_df,
    )


def _get_similarity_category(score: float) -> str:
    """Categoriza um score de similaridade de evento."""
    if score >= 0.7:
        return CustomerCategory.HIGH
    elif score >= 0.4:
        return CustomerCategory.MEDIUM
    else:
        return CustomerCategory.LOW
