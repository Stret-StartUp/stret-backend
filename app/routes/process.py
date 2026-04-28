from fastapi import APIRouter, UploadFile, File, Form
import pandas as pd

from app.services.transform import transform_data
from app.services.parser import parse_event
from app.services.scoring import score_clients
from app.services.excel import generate_excel

router = APIRouter()

@router.post("/process")
async def process_data(
    file: UploadFile = File(...),
    past_event_description: str = Form(...),
    event_description: str = Form(...)
):
    df = pd.read_excel(file.file)
    df = transform_data(df)

    current_event_features = parse_event(event_description)

    df_scored = score_clients(
        df,
        past_event_description,
        current_event_features
    )

    df_filtered = df_scored.head(100)

    return generate_excel(df_filtered)