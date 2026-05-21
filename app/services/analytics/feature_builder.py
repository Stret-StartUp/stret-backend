from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from app.core.config import settings
from app.services.ingestion.parser_service import EventFeatures


@dataclass
class CustomerFeatureBreakdown:
    event_similarity: float = 0.0
    affinity: float = 0.0
    ticket: float = 0.0
    age: float = 0.0
    purchase_timing: float = 0.0
    vibe: float = 0.0
    frequency: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.event_similarity
            + self.affinity
            + self.ticket
            + self.age
            + self.purchase_timing
            + self.vibe
            + self.frequency
        )


FEATURE_COLUMNS = [
    "event_similarity_score",
    "affinity_score",
    "ticket_score",
    "age_score",
    "purchase_timing_score",
    "vibe_score",
    "frequency_score",
    "score",
]


def build_customer_features(
    candidates_df: pd.DataFrame,
    target: EventFeatures,
) -> pd.DataFrame:
    if candidates_df.empty:
        return candidates_df.copy()

    breakdowns = candidates_df.apply(
        lambda row: _calculate_breakdown(row, target),
        axis=1,
    )

    df = candidates_df.copy()
    df["event_similarity_score"] = breakdowns.apply(lambda b: b.event_similarity)
    df["affinity_score"] = breakdowns.apply(lambda b: b.affinity)
    df["ticket_score"] = breakdowns.apply(lambda b: b.ticket)
    df["age_score"] = breakdowns.apply(lambda b: b.age)
    df["purchase_timing_score"] = breakdowns.apply(lambda b: b.purchase_timing)
    df["vibe_score"] = breakdowns.apply(lambda b: b.vibe)
    df["frequency_score"] = breakdowns.apply(lambda b: b.frequency)
    df["score"] = breakdowns.apply(lambda b: b.total)

    # Backward-compatible column names used by previous exports.
    df["similarity_score"] = df["affinity_score"]
    df["lote_score"] = df["purchase_timing_score"]
    return df


def _calculate_breakdown(row: pd.Series, target: EventFeatures) -> CustomerFeatureBreakdown:
    return CustomerFeatureBreakdown(
        event_similarity=_event_similarity_score(row) * settings.EVENT_SIMILARITY_WEIGHT,
        affinity=_affinity_score(row, target) * settings.AFFINITY_WEIGHT,
        ticket=_ticket_score(row.get("valor_medio"), target.price) * settings.TICKET_WEIGHT,
        age=_age_score(row.get("idade"), target) * settings.AGE_WEIGHT,
        purchase_timing=_purchase_timing_score(row.get("eventos_passados", []))
        * settings.PURCHASE_TIMING_WEIGHT,
        vibe=_vibe_score(row, target) * settings.VIBE_WEIGHT,
        frequency=_frequency_score(row.get("freq_compra")) * settings.FREQUENCY_WEIGHT,
    )


def _event_similarity_score(row: pd.Series) -> float:
    if not _is_null(row.get("weighted_event_similarity")):
        return float(row.get("weighted_event_similarity"))
    if not _is_null(row.get("max_event_similarity")):
        return float(row.get("max_event_similarity"))
    if not _is_null(row.get("avg_event_similarity")):
        return float(row.get("avg_event_similarity"))
    return 0.0


def _affinity_score(row: pd.Series, target: EventFeatures) -> float:
    target_terms = _normalized_terms(target.keywords)
    if not target_terms:
        return 0.0

    row_terms = _normalized_terms(
        [
            row.get("historical_event_description"),
            row.get("historical_event_category"),
            row.get("historical_event_location"),
            row.get("historical_event_size"),
            row.get("historical_event_vibe"),
            row.get("historical_event_audience_type"),
            row.get("cidade"),
            row.get("faculdade"),
            *_as_list(row.get("eventos_passados")),
            *_as_list(row.get("historical_event_colleges")),
            *_as_list(row.get("historical_event_genres")),
            *_as_list(row.get("historical_event_themes")),
            *_as_list(row.get("historical_event_artists")),
            *_as_list(row.get("historical_event_brands")),
        ]
    )

    matches = sum(1 for term in target_terms if _contains_term(term, row_terms))
    return matches / len(target_terms)


def _ticket_score(valor_medio, target_price) -> float:
    if _is_null(valor_medio) or _is_null(target_price):
        return 0.0

    historical_price = float(valor_medio)
    target = float(target_price)

    if historical_price <= 0 or target <= 0:
        return 0.0

    distance = abs(historical_price - target) / target
    return max(0.0, 1.0 - distance)


def _age_score(idade, features: EventFeatures) -> float:
    if _is_null(idade):
        return 0.0
    return 1.0 if features.idade_min <= int(idade) <= features.idade_max else 0.0


def _purchase_timing_score(eventos_passados) -> float:
    eventos = _as_list(eventos_passados)
    if not eventos:
        return 0.0

    lote_scores = {
        "promocional": 1.0,
        "primeiro lote": 1.0,
        "1o": 1.0,
        "1º": 1.0,
        "1°": 1.0,
        "segundo lote": 0.7,
        "2o": 0.7,
        "2º": 0.7,
        "2°": 0.7,
        "terceiro lote": 0.5,
        "3o": 0.5,
        "3º": 0.5,
        "3°": 0.5,
        "vip": 0.8,
        "camarote": 0.8,
    }

    total = 0.0
    valid_count = 0

    for evento in eventos:
        if _is_null(evento):
            continue
        text = _normalize(evento)
        total += next((score for key, score in lote_scores.items() if key in text), 0.3)
        valid_count += 1

    return total / valid_count if valid_count else 0.0


def _vibe_score(row: pd.Series, target: EventFeatures) -> float:
    if not target.vibe:
        return 0.0

    target_vibe = _normalize(target.vibe)
    row_terms = _normalized_terms(
        [
            row.get("historical_event_vibe"),
            row.get("historical_event_description"),
            *_as_list(row.get("eventos_passados")),
        ]
    )

    if _contains_term(target_vibe, row_terms):
        return 1.0

    valor_medio = row.get("valor_medio")
    if target_vibe == "premium" and not _is_null(valor_medio) and float(valor_medio) >= 150:
        return 0.7

    if target_vibe == "sujeira" and not _is_null(valor_medio) and float(valor_medio) <= 80:
        return 0.6

    return 0.0


def _frequency_score(freq_compra) -> float:
    if _is_null(freq_compra):
        return 0.0
    return min(int(freq_compra) * 0.05, 1.0)


def _as_list(value) -> list:
    if _is_null(value):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _normalized_terms(values: Iterable) -> list[str]:
    terms = []
    for value in values:
        if _is_null(value):
            continue
        normalized = _normalize(value)
        if normalized:
            terms.append(normalized)
    return terms


def _contains_term(target_term: str, row_terms: list[str]) -> bool:
    return any(target_term in term or term in target_term for term in row_terms)


def _normalize(value) -> str:
    if _is_null(value):
        return ""
    return str(value).strip().lower()


def _is_null(value) -> bool:
    if value is None:
        return True

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
