from app.db.base import Base
from app.db.session import get_engine

# Importar todos os models para o metadata ser populado
from app.models import user, event, customer, analysis, ranking  # noqa: F401


async def init_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


if __name__ == "__main__":
    import asyncio

    asyncio.run(init_db())
