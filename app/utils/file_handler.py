import pandas as pd

def validate_dataframe(df: pd.DataFrame):
    required_columns = ["idade", "interesse"]

    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Coluna obrigatória ausente: {col}")

    return True