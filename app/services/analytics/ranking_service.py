"""
Orquestra o pipeline completo de scoring e persistência do ranking.
"""
from typing import List

import pandas as pd

from app.models.ranking import Ranking
from app.services.ingestion.parser_service import parse_event
from app.services.analytics.scoring_service import score_clients


def build_rankings(
    df: pd.DataFrame,
    past_descriptions: str,
    target_event_description: str,
    analysis_id: int,
    top_n: int = 100,
) -> List[Ranking]:
    """
    Executa o scoring e retorna uma lista de objetos Ranking prontos para persistir.
    """
    current_features = parse_event(target_event_description)
    df_scored = score_clients(df, [parse_event(past_descriptions)], current_features)
    df_top = df_scored.head(top_n).reset_index(drop=True)

    rankings = []
    for position, (_, row) in enumerate(df_top.iterrows(), start=1):
        rankings.append(
            Ranking(
                analysis_id=analysis_id,
                email=row["email"],
                score=round(row["score"], 4),
                position=position,
                similarity_score=round(row.get("similarity_score", 0), 4),
                age_score=round(row.get("age_score", 0), 4),
                lote_score=round(row.get("lote_score", 0), 4),
                frequency_score=round(row.get("frequency_score", 0), 4),
                cidade=row.get("cidade"),
                faculdade=row.get("faculdade"),
                idade=int(row["idade"]) if pd.notnull(row.get("idade")) else None,
            )
        )
    return rankings
