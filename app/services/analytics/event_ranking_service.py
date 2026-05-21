"""
Service responsável por rankear eventos históricos por similaridade com um evento alvo.

Responsabilidades:
- Calcular score de similaridade de cada evento histórico
- Retornar eventos ranqueados com breakdown detalhado de similaridade
- Permitir filtros por score mínimo
"""

from dataclasses import dataclass

from app.models.event import Event
from app.services.analytics.event_similarity_service import (
    SimilarEvent,
    rank_similar_events,
)
from app.services.ingestion.parser_service import EventFeatures


@dataclass
class RankedEventResult:
    """Resultado do ranking de eventos."""

    similar_events: list[SimilarEvent]
    total_events: int
    events_above_threshold: int

    @property
    def ranked_events(self) -> list[SimilarEvent]:
        """Eventos ranqueados por score de similaridade (descendente)."""
        return self.similar_events


def rank_events_by_similarity(
    target: EventFeatures,
    historical_events: list[Event],
    limit: int | None = None,
    min_similarity: float = 0.0,
) -> RankedEventResult:
    """
    Rankeia eventos históricos por similaridade com evento alvo.

    Args:
        target: Características do evento alvo
        historical_events: Lista de eventos históricos
        limit: Limite de eventos a retornar (None = sem limite)
        min_similarity: Score mínimo de similaridade (0.0 a 1.0)

    Returns:
        RankedEventResult com eventos ranqueados e estatísticas
    """
    similar_events = rank_similar_events(
        target=target,
        historical_events=historical_events,
        limit=limit,
    )

    # Filtrar por similaridade mínima se necessário
    if min_similarity > 0.0:
        filtered_events = [
            event for event in similar_events if event.similarity_score >= min_similarity
        ]
    else:
        filtered_events = similar_events

    return RankedEventResult(
        similar_events=filtered_events,
        total_events=len(historical_events),
        events_above_threshold=len(filtered_events),
    )
