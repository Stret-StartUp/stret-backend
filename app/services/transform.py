import pandas as pd
from datetime import datetime


def transform_data(df: pd.DataFrame):
    df.columns = [col.strip().lower() for col in df.columns]

    df = df.rename(columns={
        "titular da compra - e-mail": "email",
        "titular da compra - data de nascimento": "data_nascimento",
        "titular da compra - cidade": "cidade",
        "titular da compra - faculdade": "faculdade",
        "valor ingresso": "valor",
        "data": "data_evento"
    })

    def safe_col(df, col):
        if col in df.columns:
            return df[col].fillna("").astype(str)
        else:
            return pd.Series([""] * len(df))


    df["evento"] = (
        safe_col(df, "grupo do ingresso") + " " +
        safe_col(df, "ingresso") + " " +
        safe_col(df, "lote") + " " +
        safe_col(df, "descricão")
    )

    df["evento"] = df["evento"].str.strip()

    df["evento"] = df["evento"].replace("", None)

    required_cols = ["email", "data_nascimento", "evento", "valor", "data_evento"]

    for col in required_cols:
        if col not in df.columns:
            raise Exception(f"Coluna obrigatória faltando: {col}")

    df["data_nascimento"] = pd.to_datetime(
        df["data_nascimento"], errors="coerce", dayfirst=True
    )

    df["data_evento"] = pd.to_datetime(
        df["data_evento"], errors="coerce", dayfirst=True
    )

    today = datetime.today()

    df["idade"] = df["data_nascimento"].apply(
        lambda x: today.year - x.year if pd.notnull(x) else None
    )

    df = df.dropna(subset=["email"])

    grouped = df.groupby("email").agg({
        "idade": "first",
        "cidade": "first",
        "faculdade": "first",
        "evento": lambda x: list(x.dropna()),
        "valor": "mean",
        "data_evento": "count"
    }).reset_index()

    grouped = grouped.rename(columns={
        "evento": "eventos_passados",
        "valor": "valor_medio",
        "data_evento": "freq_compra"
    })

    return grouped