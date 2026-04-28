from fastapi import APIRouter, UploadFile, File, Form
import pandas as pd

from app.services.transform import transform_data
from app.storage.memory_store import memory_store

router = APIRouter()

@router.post("/upload")
async def upload_data(
    file: UploadFile = File(...),
    past_event_description: str = Form(...),
    client_id: str = Form(...)
):
    df = pd.read_excel(file.file)
    df = transform_data(df)

    if client_id not in memory_store:
        memory_store[client_id] = []

    # salva
    memory_store[client_id].append({
        "data": df,
        "description": past_event_description
    })

    return {"message": "Dados armazenados com sucesso"}