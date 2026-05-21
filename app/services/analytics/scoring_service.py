import pandas as pd

from app.services.analytics.feature_builder import build_customer_features
from app.services.ingestion.parser_service import EventFeatures


def score_clients(
    df: pd.DataFrame,
    historical_events: list[EventFeatures],
    current_features: EventFeatures,
) -> pd.DataFrame:
    """Backward-compatible wrapper around the shared feature builder."""
    scored = build_customer_features(df, current_features)
    return scored.sort_values(by="score", ascending=False).reset_index(drop=True)
