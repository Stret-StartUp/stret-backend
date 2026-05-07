from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Customer(Base):
    """
    Cliente (comprador de ingresso) extraído de um evento histórico.
    Cada linha representa um cliente único por evento.
    """

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), nullable=False, index=True)

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    cidade: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    faculdade: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Dados agregados do histórico daquele evento
    eventos_passados: Mapped[list] = mapped_column(JSON, default=list)  # lista de strings
    valor_medio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    freq_compra: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relacionamentos
    event: Mapped["Event"] = relationship(back_populates="customers")  # noqa: F821