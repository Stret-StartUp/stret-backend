from dataclasses import dataclass
from typing import Optional

import pandas as pd

from app.models.event import Event
from app.services.analytics.customer_evaluation_service import evaluate_customers_from_similar_events
from app.services.analytics.customer_scoring_service import score_customers_for_target_event
from app.services.analytics.event_ranking_service import rank_events_by_similarity
from app.services.analytics.event_similarity_service import SimilarEvent
from app.services.ingestion.parser_service import EventFeatures


@dataclass
class CustomerRankingResult:
    ranked_customers: pd.DataFrame
    similar_events: list[SimilarEvent]


def rank_customers_for_event(
    target: EventFeatures,
    historical_events: list[Event],
    top_n: Optional[int] = 100,
    similar_event_limit: Optional[int] = None,
    min_event_similarity: float = 0.0,
) -> CustomerRankingResult:
    """
    Rankeia clientes para um evento alvo usando pipeline de 3 etapas:
    1. Rankear eventos por similaridade (event_ranking_service)
    2. Avaliar clientes de eventos similares (customer_evaluation_service)
    3. Gerar scores finais dos clientes (customer_scoring_service)

    Args:
        target: Características do evento alvo
        historical_events: Eventos históricos do cliente
        top_n: Número de clientes a retornar (default: 100)
        similar_event_limit: Limite de eventos similares a considerar (default: None = todos)
        min_event_similarity: Score mínimo de similaridade para incluir evento (default: 0.0)

    Returns:
        CustomerRankingResult com clientes ranqueados e eventos similares
    """
    # ETAPA 1: Rankear eventos por similaridade
    event_ranking_result = rank_events_by_similarity(
        target=target,
        historical_events=historical_events,
        limit=similar_event_limit,
        min_similarity=min_event_similarity,
    )
    similar_events = event_ranking_result.ranked_events

    if not similar_events:
        return CustomerRankingResult(
            ranked_customers=pd.DataFrame(),
            similar_events=similar_events,
        )

    # ETAPA 2: Avaliar clientes de eventos similares
    evaluation_result = evaluate_customers_from_similar_events(
        target=target,
        similar_events=similar_events,
        min_event_similarity=min_event_similarity,
    )

    if evaluation_result.all_customers.empty:
        return CustomerRankingResult(
            ranked_customers=pd.DataFrame(),
            similar_events=similar_events,
        )

    # ETAPA 3: Gerar scores finais para evento alvo
    scoring_result = score_customers_for_target_event(
        evaluated_customers_df=evaluation_result.all_customers,
        target=target,
        top_n=top_n,
    )

    ranked_customers = scoring_result.ranked_customers

    return CustomerRankingResult(
        ranked_customers=ranked_customers,
        similar_events=similar_events,
    )
