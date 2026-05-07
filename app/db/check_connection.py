import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.db.session import get_engine


async def check_connection() -> None:
    url = make_url(settings.DATABASE_URL)
    safe_target = f"{url.drivername}://{url.username}@{url.host}:{url.port}/{url.database}"

    if url.username == "user":
        raise RuntimeError(
            "DATABASE_URL ainda esta usando o placeholder 'user'. "
            "Atualize o .env com um usuario real do MySQL."
        )

    if os.getenv("DATABASE_URL"):
        print("Usando DATABASE_URL do .env. Variaveis MYSQL_* serao ignoradas.")
    else:
        print("DATABASE_URL montada a partir das variaveis MYSQL_*.")

    print(f"Testando conexao: {safe_target}")

    engine = get_engine()

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        error_detail = str(exc.orig) if getattr(exc, "orig", None) else str(exc)
        raise RuntimeError(
            "Nao foi possivel conectar ao MySQL.\n"
            f"Destino: {safe_target}\n"
            f"Erro do MySQL/driver: {error_detail}"
        ) from exc
    finally:
        await engine.dispose()

    print("Conexao MySQL ok.")


if __name__ == "__main__":
    try:
        asyncio.run(check_connection())
    except RuntimeError as exc:
        print(exc)
        sys.exit(1)
