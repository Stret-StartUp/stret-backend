from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Analysis(Base):
    """
    Análise gerada para um cliente (produtor) a partir de um evento alvo.
    Armazena o resultado do ranking e o perfil de público gerado.
    """

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    target_event_description: Mapped[str] = mapped_column(Text, nullable=False)
    profile_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    export_file_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    total_customers_analyzed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_ranked: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="pending")
    # pending | processing | done | failed

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relacionamentos
    user: Mapped["User"] = relationship(back_populates="analyses")  # noqa: F821
    rankings: Mapped[list["Ranking"]] = relationship(back_populates="analysis")  # noqa: F821