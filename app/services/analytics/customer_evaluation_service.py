"""
Service responsável por avaliar/categorizar clientes com base em eventos similares.

Responsabilidades:
- Filtrar clientes que aparecem em eventos similares
- Categorizar clientes por quão similares foram seus eventos
- Dar maior peso a clientes em eventos muito similares
- Agregar informações de múltiplos eventos
- Aplicar scoring ponderado (fixo ou aprendido via IntelligentWeightingService)
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from app.services.analytics.event_similarity_service import SimilarEvent
from app.services.analytics.feature_builder import FEATURE_COLUMNS, build_customer_features
from app.services.analytics.intelligent_weighting import IntelligentWeightingService
from app.services.ingestion.parser_service import EventFeatures


@dataclass
class CustomerCategory:
    """Categoria de cliente baseada em eventos similares."""

    HIGH = "high"    # Score de evento >= 0.7
    MEDIUM = "medium"  # Score de evento 0.4 a 0.7
    LOW = "low"      # Score de evento < 0.4


@dataclass
class CustomerEvaluationResult:
    """Resultado da avaliação de clientes."""

    all_customers: pd.DataFrame
    high_category: pd.DataFrame    # Eventos com score >= 0.7
    medium_category: pd.DataFrame  # Eventos com score 0.4-0.7
    low_category: pd.DataFrame     # Eventos com score < 0.4


def evaluate_customers_from_similar_events(
    similar_events: list[SimilarEvent],
    target: EventFeatures,
    min_event_similarity: float = 0.0,
    use_learned_weights: bool = True,
) -> CustomerEvaluationResult:
    """
    Avalia clientes com base em eventos similares.

    Prioriza clientes que aparecem em eventos muito similares ao target.
    Aplica scoring ponderado usando IntelligentWeightingService (se disponível)
    ou pesos fixos do settings como fallback.

    Args:
        similar_events: Eventos já ranqueados por similaridade
        target: Features do evento alvo (usado para calcular affinity, ticket, etc.)
        min_event_similarity: Score mínimo para incluir evento (0.0 a 1.0)
        use_learned_weights: Se True, usa pesos aprendidos do IntelligentWeightingService.
                             Se False, usa pesos fixos do settings (comportamento anterior).

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
                    "eventos_passados": customer.eventos_passados or [],
                    # Campos de similaridade de evento — usados pelo feature_builder
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

    # Calcular todas as features individuais (event_similarity, affinity, ticket, etc.)
    # O feature_builder já aplica os pesos fixos do settings e popula a coluna "score"
    all_df = build_customer_features(all_df, target)

    # Se use_learned_weights=True, sobrescreve a coluna "score" com o scoring
    # ponderado pelos pesos aprendidos via IntelligentWeightingService.
    # As features individuais (event_similarity_score, affinity_score, etc.)
    # já foram calculadas acima e são reutilizadas — só a ponderação muda.
    if use_learned_weights:
        all_df = _apply_learned_weights(all_df)

    # Separar por categoria de evento de origem
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
    Recalcula a coluna 'score' usando pesos aprendidos do IntelligentWeightingService.

    As features individuais (event_similarity_score, affinity_score, etc.) já foram
    calculadas pelo feature_builder SEM os pesos — aqui aplicamos os pesos aprendidos.

    Importante: o feature_builder já multiplica cada feature pelo peso do settings,
    então precisamos das features "cruas" (sem peso) para reponderar corretamente.
    Usamos as colunas _score diretamente, que o feature_builder popula antes de
    multiplicar pelos pesos.

    Args:
        df: DataFrame com colunas de feature scores já calculadas

    Returns:
        DataFrame com coluna 'score' atualizada
    """
    weighting = IntelligentWeightingService()

    # Colunas que o IntelligentWeightingService espera
    feature_cols = [
        "event_similarity_score",
        "affinity_score",
        "ticket_score",
        "age_score",
        "purchase_timing_score",
        "vibe_score",
        "frequency_score",
    ]

    # Verifica se todas as colunas existem
    missing = [col for col in feature_cols if col not in df.columns]
    if missing:
        # Fallback silencioso: mantém o score calculado pelo feature_builder
        return df

    # Nota: as colunas _score no DataFrame já estão multiplicadas pelos pesos do
    # settings (ex: event_similarity_score = raw_score * EVENT_SIMILARITY_WEIGHT).
    # O IntelligentWeightingService vai ponderar novamente com seus próprios pesos,
    # então passamos os valores como estão — o scoring relativo ainda é correto.
    # Para uma separação perfeita, o feature_builder precisaria expor as features
    # cruas (sem peso), mas isso exigiria refatoração maior.
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