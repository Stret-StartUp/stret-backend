from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class AnalysisCreate(BaseModel):
    client_id: str
    target_event_description: str


class RankingItemOut(BaseModel):
    email: str
    score: float
    position: int
    similarity_score: Optional[float]
    age_score: Optional[float]
    lote_score: Optional[float]
    frequency_score: Optional[float]
    cidade: Optional[str]
    faculdade: Optional[str]
    idade: Optional[int]

    model_config = {"from_attributes": True}


class AnalysisOut(BaseModel):
    id: int
    client_id: str
    target_event_description: str
    profile_text: Optional[str]
    status: str
    total_customers_analyzed: Optional[int]
    total_ranked: Optional[int]
    created_at: datetime
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


class AnalysisWithRankings(AnalysisOut):
    rankings: List[RankingItemOut] = []


class ProfileOut(BaseModel):
    profile: str