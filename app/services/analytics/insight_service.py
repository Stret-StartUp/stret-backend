from collections import Counter
from typing import Optional

import pandas as pd

from app.services.ingestion.parser_service import EventFeatures, event_features_to_text


def generate_profile_text(
    df: pd.DataFrame,
    target_features: EventFeatures,
    historical_events: Optional[list[EventFeatures]] = None,
) -> str:
    historical_events = historical_events or []

    idade_media = df["idade"].mean()
    idade_min = df["idade"].min()
    idade_max = df["idade"].max()
    valor_medio = df["valor_medio"].mean()
    freq_media = df["freq_compra"].mean()
    lote_preferido = _preferred_purchase_timing(df)
    qualidade = _preferred_quality(df, historical_events)

    top_colleges = _top_values(df, "faculdade", 3)
    top_cities = _top_values(df, "cidade", 3)
    top_genres = _top_event_terms(historical_events, "genres", 5)
    top_themes = _top_event_terms(historical_events, "themes", 5)
    top_artists = _top_event_terms(historical_events, "artists", 5)
    top_brands = _top_event_terms(historical_events, "brands", 5)
    top_categories = _top_scalar_terms(historical_events, "category", 3)
    top_vibes = _top_scalar_terms(historical_events, "vibe", 3)

    parts = ["Perfil historico de consumidor: "]

    if top_categories:
        parts.append(f"costuma participar de eventos de {', '.join(top_categories)}. ")

    if top_genres:
        parts.append(f"Generos mais fortes: {', '.join(top_genres)}. ")

    if top_themes:
        parts.append(f"Temas recorrentes: {', '.join(top_themes)}. ")

    if top_artists or top_brands:
        interests = [*top_artists, *top_brands]
        parts.append(f"Interesses detectados: {', '.join(interests[:6])}. ")

    if pd.notnull(valor_medio):
        parts.append(f"Ticket medio historico em torno de R${int(valor_medio)}. ")

    if lote_preferido:
        parts.append(f"Padrao de compra: maior aderencia a {lote_preferido}. ")

    if pd.notnull(idade_media):
        parts.append(f"Idade media de {int(idade_media)} anos")
        if pd.notnull(idade_min) and pd.notnull(idade_max):
            parts.append(f", variando entre {int(idade_min)} e {int(idade_max)}")
        parts.append(". ")

    if top_colleges:
        parts.append(f"Faculdades mais presentes: {', '.join(top_colleges)}. ")

    if top_cities:
        parts.append(f"Cidades mais presentes: {', '.join(top_cities)}. ")

    if qualidade:
        parts.append(f"Qualidade/vibe preferida: {qualidade}. ")

    if pd.notnull(freq_media):
        parts.append(f"Frequencia media de compra: {round(freq_media, 1)} eventos. ")

    target_text = event_features_to_text(target_features)
    if target_text:
        parts.append(_target_fit_sentence(target_features, top_colleges, top_genres, top_vibes))

    return "".join(parts).strip()


def generate_segment_stats(df: pd.DataFrame) -> dict:
    return {
        "total_customers": len(df),
        "avg_age": round(df["idade"].mean(), 1) if "idade" in df.columns else None,
        "avg_ticket": round(df["valor_medio"].mean(), 2) if "valor_medio" in df.columns else None,
        "avg_frequency": round(df["freq_compra"].mean(), 2) if "freq_compra" in df.columns else None,
        "top_cities": (
            df["cidade"].dropna().value_counts().head(5).to_dict()
            if "cidade" in df.columns else {}
        ),
        "top_colleges": (
            df["faculdade"].dropna().value_counts().head(5).to_dict()
            if "faculdade" in df.columns else {}
        ),
    }


def _target_fit_sentence(
    target: EventFeatures,
    top_colleges: list[str],
    top_genres: list[str],
    top_vibes: list[str],
) -> str:
    matches = []

    if target.is_universitario and top_colleges:
        matches.append("base universitaria forte")

    if target.genres and any(genre in top_genres for genre in target.genres):
        matches.append("genero musical ja validado no historico")

    if target.vibe and target.vibe in top_vibes:
        matches.append("vibe alinhada com eventos anteriores")

    if not matches:
        return "Para o evento alvo, priorize clientes com maior score por proximidade historica. "

    return f"Para o evento alvo, ha sinais de {', '.join(matches)}. "


def _preferred_purchase_timing(df: pd.DataFrame) -> Optional[str]:
    if "eventos_passados" not in df.columns:
        return None

    counts = Counter()

    for eventos in df["eventos_passados"].dropna():
        if not isinstance(eventos, list):
            eventos = [eventos]
        for evento in eventos:
            text = str(evento).lower()
            if any(term in text for term in ["promocional", "1o", "1º", "1°", "primeiro"]):
                counts["lotes iniciais"] += 1
            elif any(term in text for term in ["2o", "2º", "2°", "segundo"]):
                counts["lotes intermediarios"] += 1
            elif any(term in text for term in ["3o", "3º", "3°", "terceiro"]):
                counts["lotes finais"] += 1

    return counts.most_common(1)[0][0] if counts else None


def _preferred_quality(
    df: pd.DataFrame,
    historical_events: list[EventFeatures],
) -> Optional[str]:
    vibes = _top_scalar_terms(historical_events, "vibe", 1)
    if vibes:
        return vibes[0]

    if "valor_medio" not in df.columns:
        return None

    avg_ticket = df["valor_medio"].mean()
    if pd.isna(avg_ticket):
        return None
    if avg_ticket >= 150:
        return "premium"
    if avg_ticket <= 80:
        return "mais popular/sujeira"
    return "intermediaria"


def _top_values(df: pd.DataFrame, column: str, limit: int) -> list[str]:
    if column not in df.columns:
        return []
    return [str(value) for value in df[column].dropna().value_counts().head(limit).index.tolist()]


def _top_event_terms(
    events: list[EventFeatures],
    attr: str,
    limit: int,
) -> list[str]:
    counter = Counter()
    for event in events:
        counter.update(getattr(event, attr, []) or [])
    return [term for term, _ in counter.most_common(limit)]


def _top_scalar_terms(
    events: list[EventFeatures],
    attr: str,
    limit: int,
) -> list[str]:
    counter = Counter()
    for event in events:
        value = getattr(event, attr, None)
        if value:
            counter[value] += 1
    return [term for term, _ in counter.most_common(limit)]
