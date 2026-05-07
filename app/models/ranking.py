from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Ranking(Base):
    """
    Resultado de score para um cliente específico dentro de uma análise.
    """

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analysis.id"), nullable=False, index=True)

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Detalhamento do score (para auditoria)
    similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    age_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lote_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    frequency_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    cidade: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    faculdade: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relacionamentos
    analysis: Mapped["Analysis"] = relationship(back_populates="rankings")  # noqa: F821