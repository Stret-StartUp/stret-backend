from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from app.core.config import settings
from app.services.ingestion.parser_service import EventFeatures


@dataclass
class ScoreBreakdown:
    affinity: float = 0.0
    ticket: float = 0.0
    age: float = 0.0
    purchase_timing: float = 0.0
    vibe: float = 0.0
    frequency: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.affinity
            + self.ticket
            + self.age
            + self.purchase_timing
            + self.vibe
            + self.frequency
        )


def score_clients(
    df: pd.DataFrame,
    historical_events: list[EventFeatures],
    current_features: EventFeatures,
) -> pd.DataFrame:
    breakdowns = df.apply(
        lambda row: _calculate_breakdown(row, historical_events, current_features),
        axis=1,
    )

    df = df.copy()
    df["affinity_score"] = breakdowns.apply(lambda b: b.affinity)
    df["ticket_score"] = breakdowns.apply(lambda b: b.ticket)
    df["age_score"] = breakdowns.apply(lambda b: b.age)
    df["purchase_timing_score"] = breakdowns.apply(lambda b: b.purchase_timing)
    df["vibe_score"] = breakdowns.apply(lambda b: b.vibe)
    df["frequency_score"] = breakdowns.apply(lambda b: b.frequency)

    # Backward-compatible column names used by previous exports.
    df["similarity_score"] = df["affinity_score"]
    df["lote_score"] = df["purchase_timing_score"]
    df["score"] = breakdowns.apply(lambda b: b.total)

    return df.sort_values(by="score", ascending=False).reset_index(drop=True)


def _calculate_breakdown(
    row: pd.Series,
    historical_events: list[EventFeatures],
    target: EventFeatures,
) -> ScoreBreakdown:
    event_context = _row_event_context(row, historical_events)

    return ScoreBreakdown(
        affinity=_affinity_score(row, event_context, target) * settings.AFFINITY_WEIGHT,
        ticket=_ticket_score(row.get("valor_medio"), target.price) * settings.TICKET_WEIGHT,
        age=_age_score(row.get("idade"), target) * settings.AGE_WEIGHT,
        purchase_timing=_purchase_timing_score(row.get("eventos_passados", []))
        * settings.PURCHASE_TIMING_WEIGHT,
        vibe=_vibe_score(row, event_context, target) * settings.VIBE_WEIGHT,
        frequency=_frequency_score(row.get("freq_compra")) * settings.FREQUENCY_WEIGHT,
    )


def _affinity_score(
    row: pd.Series,
    event_context: list[str],
    target: EventFeatures,
) -> float:
    target_terms = _normalized_terms(target.keywords)
    if not target_terms:
        return 0.0

    row_terms = _normalized_terms(
        [
            *event_context,
            row.get("cidade"),
            row.get("faculdade"),
            *_as_list(row.get("eventos_passados")),
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


def _vibe_score(
    row: pd.Series,
    event_context: list[str],
    target: EventFeatures,
) -> float:
    if not target.vibe:
        return 0.0

    target_vibe = _normalize(target.vibe)
    row_terms = _normalized_terms([*event_context, *_as_list(row.get("eventos_passados"))])

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


def _row_event_context(row: pd.Series, historical_events: list[EventFeatures]) -> list[str]:
    row_context = [
        row.get("historical_event_description"),
        row.get("historical_event_category"),
        row.get("historical_event_location"),
        row.get("historical_event_size"),
        row.get("historical_event_vibe"),
        row.get("historical_event_audience_type"),
        *_as_list(row.get("historical_event_colleges")),
        *_as_list(row.get("historical_event_genres")),
        *_as_list(row.get("historical_event_themes")),
        *_as_list(row.get("historical_event_artists")),
        *_as_list(row.get("historical_event_brands")),
    ]

    if any(not _is_null(value) for value in row_context):
        return [str(value) for value in row_context if not _is_null(value)]

    return [
        value
        for event in historical_events
        for value in [*event.keywords, event.description]
        if value
    ]


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
