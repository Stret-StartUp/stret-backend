from io import BytesIO

import pandas as pd
from fastapi.responses import StreamingResponse


EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def validate_dataframe(df: pd.DataFrame):
    required_columns = ["idade", "interesse"]

    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Coluna obrigatória ausente: {col}")

    return True


def generate_excel(df: pd.DataFrame, filename: str = "ranking.xlsx") -> StreamingResponse:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="ranking")

    output.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(output, media_type=EXCEL_MEDIA_TYPE, headers=headers)
