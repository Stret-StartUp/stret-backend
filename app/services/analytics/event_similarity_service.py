import unicodedata
from dataclasses import asdict, dataclass
from typing import Iterable, Optional, Sequence

from app.models.event import Event
from app.services.ingestion.parser_service import EventFeatures, deserialize_event_features


@dataclass
class EventSimilarityBreakdown:
    category: float = 0.0
    price: float = 0.0
    location: float = 0.0
    size: float = 0.0
    vibe: float = 0.0
    audience: float = 0.0
    colleges: float = 0.0
    genres: float = 0.0
    themes: float = 0.0
    artists: float = 0.0
    brands: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SimilarEvent:
    event: Event
    features: EventFeatures
    similarity_score: float
    breakdown: EventSimilarityBreakdown

    @property
    def event_id(self) -> int:
        return self.event.id

    @property
    def client_id(self) -> str:
        return self.event.client_id

    @property
    def customer_count(self) -> int:
        return len(self.event.customers or [])


EVENT_SIMILARITY_WEIGHTS = {
    "category": 0.18,
    "price": 0.14,
    "location": 0.10,
    "size": 0.08,
    "vibe": 0.14,
    "audience": 0.12,
    "colleges": 0.08,
    "genres": 0.08,
    "themes": 0.04,
    "artists": 0.02,
    "brands": 0.02,
}


def rank_similar_events(
    target: EventFeatures,
    historical_events: Sequence[Event],
    limit: Optional[int] = None,
) -> list[SimilarEvent]:
    ranked_events = [
        _score_event_similarity(target, event)
        for event in historical_events
    ]

    ranked_events.sort(key=lambda item: item.similarity_score, reverse=True)

    if limit is not None:
        return ranked_events[:limit]

    return ranked_events


def _score_event_similarity(target: EventFeatures, event: Event) -> SimilarEvent:
    historical = deserialize_event_features(event.description)
    breakdown = EventSimilarityBreakdown(
        category=_text_score(target.category, historical.category),
        price=_price_score(target.price, historical.price),
        location=_text_score(target.location, historical.location),
        size=_text_score(target.size, historical.size),
        vibe=_text_score(target.vibe, historical.vibe),
        audience=_text_score(target.audience_type, historical.audience_type),
        colleges=_list_score(target.colleges, historical.colleges),
        genres=_list_score(target.genres, historical.genres),
        themes=_list_score(target.themes, historical.themes),
        artists=_list_score(target.artists, historical.artists),
        brands=_list_score(target.brands, historical.brands),
    )

    total = sum(
        getattr(breakdown, field) * weight
        for field, weight in EVENT_SIMILARITY_WEIGHTS.items()
    )

    return SimilarEvent(
        event=event,
        features=historical,
        similarity_score=round(total, 6),
        breakdown=breakdown,
    )


def _text_score(target_value: Optional[str], historical_value: Optional[str]) -> float:
    target = _normalize(target_value)
    historical = _normalize(historical_value)

    if not target or not historical:
        return 0.0

    if target == historical:
        return 1.0

    if target in historical or historical in target:
        return 0.7

    return 0.0


def _price_score(target_price: Optional[float], historical_price: Optional[float]) -> float:
    if target_price is None or historical_price is None:
        return 0.0

    target = float(target_price)
    historical = float(historical_price)

    if target <= 0 or historical <= 0:
        return 0.0

    distance = abs(target - historical) / max(target, historical)
    return max(0.0, 1.0 - distance)


def _list_score(target_values: Iterable[str], historical_values: Iterable[str]) -> float:
    target = set(_normalized_terms(target_values))
    historical = set(_normalized_terms(historical_values))

    if not target or not historical:
        return 0.0

    intersection = target.intersection(historical)
    union = target.union(historical)
    return len(intersection) / len(union)


def _normalized_terms(values: Iterable[str]) -> list[str]:
    return [
        normalized
        for value in values or []
        if (normalized := _normalize(value))
    ]


def _normalize(value) -> str:
    if value is None:
        return ""

    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(char for char in text if not unicodedata.combining(char))
