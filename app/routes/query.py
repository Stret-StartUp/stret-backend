from fastapi import APIRouter, Form
import pandas as pd

from app.storage.memory_store import memory_store
from app.services.parser import parse_event
from app.services.scoring import score_clients
from app.services.excel import generate_excel

router = APIRouter()

@router.post("/query")
async def query_data(
    client_id: str = Form(...),
    event_description: str = Form(...)
):
    if client_id not in memory_store:
        return {"error": "Nenhum dado encontrado para esse cliente"}

    dfs = [item["data"] for item in memory_store[client_id]]
    full_df = pd.concat(dfs, ignore_index=True)

    past_descriptions = " ".join(
        [item["description"] for item in memory_store[client_id]]
    )

    current_event_features = parse_event(event_description)

    df_scored = score_clients(
        full_df,
        past_descriptions,
        current_event_features
    )

    df_filtered = df_scored.head(100)

    return generate_excel(df_filtered)