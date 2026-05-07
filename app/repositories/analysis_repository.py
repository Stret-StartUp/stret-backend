from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import Analysis
from app.models.ranking import Ranking


class AnalysisRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, client_id: str, target_event_description: str) -> Analysis:
        analysis = Analysis(
            user_id=user_id,
            client_id=client_id,
            target_event_description=target_event_description,
            status="pending",
        )
        self.db.add(analysis)
        await self.db.commit()
        await self.db.refresh(analysis)
        return analysis

    async def get_by_id(self, analysis_id: int) -> Optional[Analysis]:
        result = await self.db.execute(
            select(Analysis)
            .where(Analysis.id == analysis_id)
            .options(selectinload(Analysis.rankings))
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: int) -> List[Analysis]:
        result = await self.db.execute(
            select(Analysis)
            .where(Analysis.user_id == user_id)
            .order_by(Analysis.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(self, analysis_id: int, status: str, **kwargs) -> None:
        result = await self.db.execute(select(Analysis).where(Analysis.id == analysis_id))
        analysis = result.scalar_one_or_none()
        if analysis:
            analysis.status = status
            for key, value in kwargs.items():
                setattr(analysis, key, value)
            if status in ("done", "failed"):
                analysis.finished_at = datetime.utcnow()
            await self.db.commit()

    async def save_rankings(self, rankings: List[Ranking]) -> None:
        self.db.add_all(rankings)
        await self.db.commit()