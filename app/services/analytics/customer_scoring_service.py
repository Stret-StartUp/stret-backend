"""
Service responsável por gerar scores finais de clientes para um evento alvo.

Responsabilidades:
- Agregar clientes por email (podem aparecer em múltiplos eventos)
- Dar peso diferente baseado em QUAL EVENTO apareceram (eventos similares = mais peso)
- Calcular score final considerando:
  * Similaridade dos eventos onde aparecem
  * Características do cliente (idade, valor gasto, frequência)
  * Compatibilidade com evento alvo (afinidade, preço, vibe)

Integração com Intelligent Weighting:
- Usa pesos aprendíveis do IntelligentWeightingService
- Permite otimizar pesos com histórico de compras reais
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from app.services.analytics.feature_builder import (
    CustomerFeatureBreakdown,
    _affinity_score,
    _age_score,
    _frequency_score,
    _purchase_timing_score,
    _ticket_score,
    _vibe_score,
)
from app.services.analytics.intelligent_weighting import IntelligentWeightingService
from app.services.ingestion.parser_service import EventFeatures


@dataclass
class CustomerScoringResult:
    """Resultado do scoring final de clientes."""

    ranked_customers: pd.DataFrame
    total_customers: int
    customers_scored: int


def score_customers_for_target_event(
    evaluated_customers_df: pd.DataFrame,
    target: EventFeatures,
    top_n: Optional[int] = 100,
    high_category_weight: float = 1.0,
    medium_category_weight: float = 0.7,
    low_category_weight: float = 0.3,
) -> CustomerScoringResult:
    """
    Gera scores finais para clientes com base em evento alvo.

    Prioriza clientes de eventos similares (high_category) e pondera
    os demais pela categoria do evento em que aparecem.

    Args:
        evaluated_customers_df: DataFrame com clientes já categorizados
        target: Características do evento alvo
        top_n: Retornar apenas top N clientes (None = todos)
        high_category_weight: Multiplicador para clientes em eventos muito similares
        medium_category_weight: Multiplicador para clientes em eventos medianamente similares
        low_category_weight: Multiplicador para clientes em eventos pouco similares

    Returns:
        CustomerScoringResult com clientes ranqueados e scores
    """
    if evaluated_customers_df.empty:
        return CustomerScoringResult(
            ranked_customers=pd.DataFrame(),
            total_customers=0,
            customers_scored=0,
        )

    # Agregar clientes por email (podem aparecer em múltiplos eventos)
    aggregated = _aggregate_customers_by_email(
        evaluated_customers_df,
        high_category_weight=high_category_weight,
        medium_category_weight=medium_category_weight,
        low_category_weight=low_category_weight,
    )

    if aggregated.empty:
        return CustomerScoringResult(
            ranked_customers=aggregated,
            total_customers=0,
            customers_scored=0,
        )

    # Calcular scores brutos + score final ponderado via IntelligentWeightingService
    aggregated = _calculate_customer_scores(aggregated, target)

    # Ordenar por score decrescente
    aggregated = aggregated.sort_values(
        by=["score", "event_similarity_weighted", "frequency_score"],
        ascending=False,
    ).reset_index(drop=True)

    if top_n is not None:
        aggregated = aggregated.head(top_n)

    return CustomerScoringResult(
        ranked_customers=aggregated,
        total_customers=len(evaluated_customers_df["email_normalized"].unique()),
        customers_scored=len(aggregated),
    )


def _aggregate_customers_by_email(
    df: pd.DataFrame,
    high_category_weight: float = 1.0,
    medium_category_weight: float = 0.7,
    low_category_weight: float = 0.3,
) -> pd.DataFrame:
    """Agrega múltiplos registros do mesmo cliente com ponderação por categoria."""
    records = []

    for email, group in df.groupby("email_normalized"):
        high_scores = group[group["event_category"] == "high"]["event_similarity_score"]
        medium_scores = group[group["event_category"] == "medium"]["event_similarity_score"]
        low_scores = group[group["event_category"] == "low"]["event_similarity_score"]

        weighted_sum = (
            (high_scores.sum() * high_category_weight)
            + (medium_scores.sum() * medium_category_weight)
            + (low_scores.sum() * low_category_weight)
        )

        total_weight = (
            (len(high_scores) * high_category_weight)
            + (len(medium_scores) * medium_category_weight)
            + (len(low_scores) * low_category_weight)
        )

        event_similarity_weighted = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Agrega eventos_passados de todos os registros do cliente
        all_eventos_passados = []
        for ep in group["eventos_passados"].dropna():
            if isinstance(ep, list):
                all_eventos_passados.extend(ep)
            elif ep:
                all_eventos_passados.append(ep)

        records.append(
            {
                "email": group["email"].iloc[0],
                "email_normalized": email,
                "idade": group["idade"].iloc[0] if not group["idade"].isna().all() else None,
                "cidade": group["cidade"].mode()[0] if not group["cidade"].isna().all() else None,
                "faculdade": group["faculdade"].mode()[0] if not group["faculdade"].isna().all() else None,
                "valor_medio": group["valor_medio"].mean() if not group["valor_medio"].isna().all() else None,
                "freq_compra": group["freq_compra"].sum() if not group["freq_compra"].isna().all() else 0,
                "eventos_passados": all_eventos_passados,  # preservado para purchase_timing_score
                "event_count": len(group),
                "high_category_count": len(high_scores),
                "medium_category_count": len(medium_scores),
                "low_category_count": len(low_scores),
                "event_similarity_scores": group["event_similarity_score"].tolist(),
                "event_similarity_weighted": event_similarity_weighted,
                "event_similarity_max": group["event_similarity_score"].max(),
                "event_similarity_avg": group["event_similarity_score"].mean(),
                # Campos históricos do evento de maior similaridade (para vibe/affinity)
                "historical_event_vibe": group.loc[group["event_similarity_score"].idxmax(), "historical_event_vibe"]
                    if "historical_event_vibe" in group.columns else None,
                "historical_event_description": group.loc[group["event_similarity_score"].idxmax(), "historical_event_description"]
                    if "historical_event_description" in group.columns else None,
            }
        )

    return pd.DataFrame(records) if records else pd.DataFrame()


def _calculate_customer_scores(
    aggregated_df: pd.DataFrame,
    target: EventFeatures,
) -> pd.DataFrame:
    """
    Calcula scores BRUTOS para cada feature e score final via IntelligentWeightingService.

    Não aplica pesos manualmente — toda a ponderação fica no WeightingService,
    evitando double-weighting.
    """
    df = aggregated_df.copy()

    # Scores brutos (0–1), sem multiplicar por nenhum peso
    df["event_similarity_score"] = df["event_similarity_weighted"]

    df["affinity_score"] = df.apply(
        lambda row: _affinity_score(row, target),
        axis=1,
    )

    df["ticket_score"] = df.apply(
        lambda row: _ticket_score(row.get("valor_medio"), target.price),
        axis=1,
    )

    df["age_score"] = df.apply(
        lambda row: _age_score(row.get("idade"), target),
        axis=1,
    )

    df["frequency_score"] = df.apply(
        lambda row: _frequency_score(row.get("freq_compra")),
        axis=1,
    )

    # CORRIGIDO: usa eventos_passados do cliente, não lista vazia hardcoded
    df["purchase_timing_score"] = df.apply(
        lambda row: _purchase_timing_score(row.get("eventos_passados", [])),
        axis=1,
    )

    df["vibe_score"] = df.apply(
        lambda row: _vibe_score(row, target),
        axis=1,
    )

    # Score final: única ponderação, feita pelo IntelligentWeightingService
    weighting_service = IntelligentWeightingService()

    features_list = [
        {
            "event_similarity_score": row["event_similarity_score"],
            "affinity_score": row["affinity_score"],
            "ticket_score": row["ticket_score"],
            "age_score": row["age_score"],
            "frequency_score": row["frequency_score"],
            "purchase_timing_score": row["purchase_timing_score"],
            "vibe_score": row["vibe_score"],
        }
        for _, row in df.iterrows()
    ]

    df["score"] = weighting_service.batch_score(features_list)

    return df
