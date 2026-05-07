"""
Responsável por normalizar o DataFrame bruto do Excel
para o schema interno da aplicação.
"""
import pandas as pd
from datetime import datetime

from app.utils.logger import logger


COLUMN_MAP = {
    "titular da compra - e-mail": "email",
    "titular da compra - data de nascimento": "data_nascimento",
    "titular da compra - cidade": "cidade",
    "titular da compra - faculdade": "faculdade",
    "valor ingresso": "valor",
    "data": "data_evento",
}

REQUIRED_COLUMNS = ["email", "data_nascimento", "valor", "data_evento"]


def transform_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normaliza colunas, calcula idade, agrega por email.
    Retorna um DataFrame com uma linha por cliente único.
    """
    df = _normalize_columns(df)
    df = _rename_columns(df)
    df = _validate_required(df)
    df = _build_evento_column(df)
    df = _parse_dates(df)
    df = _calculate_age(df)
    df = _drop_invalid(df)
    df = _aggregate_by_customer(df)
    return df


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [col.strip().lower() for col in df.columns]
    return df


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=COLUMN_MAP)


def _validate_required(df: pd.DataFrame) -> pd.DataFrame:
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            raise ValueError(f"Coluna obrigatória ausente no arquivo: '{col}'")
    return df


def _safe_col(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return df[col].fillna("").astype(str)
    return pd.Series([""] * len(df), index=df.index)


def _build_evento_column(df: pd.DataFrame) -> pd.DataFrame:
    parts = ["grupo do ingresso", "ingresso", "lote", "descricão"]
    combined = (
        _safe_col(df, parts[0]) + " " +
        _safe_col(df, parts[1]) + " " +
        _safe_col(df, parts[2]) + " " +
        _safe_col(df, parts[3])
    ).str.strip()
    df["evento"] = combined.replace("", None)
    return df


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    df["data_nascimento"] = pd.to_datetime(df["data_nascimento"], errors="coerce", dayfirst=True)
    df["data_evento"] = pd.to_datetime(df["data_evento"], errors="coerce", dayfirst=True)
    return df


def _calculate_age(df: pd.DataFrame) -> pd.DataFrame:
    today = datetime.today()
    df["idade"] = df["data_nascimento"].apply(
        lambda x: today.year - x.year if pd.notnull(x) else None
    )
    return df


def _drop_invalid(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.dropna(subset=["email"])
    after = len(df)
    if before != after:
        logger.warning(f"Removidas {before - after} linhas sem e-mail.")
    return df


def _aggregate_by_customer(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("email").agg(
        idade=("idade", "first"),
        cidade=("cidade", "first"),
        faculdade=("faculdade", "first"),
        eventos_passados=("evento", lambda x: list(x.dropna())),
        valor_medio=("valor", "mean"),
        freq_compra=("data_evento", "count"),
    ).reset_index()
    return grouped