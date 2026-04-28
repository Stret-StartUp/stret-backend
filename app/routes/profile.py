from fastapi import APIRouter, Form
import pandas as pd

from app.storage.memory_store import memory_store
from app.services.parser import parse_event

router = APIRouter()


@router.post("/profile")
async def generate_profile(
    client_id: str = Form(...),
    event_description: str = Form(...)
):
    if client_id not in memory_store:
        return {"error": "Nenhum dado encontrado para esse cliente"}

    dfs = [item["data"] for item in memory_store[client_id]]
    df = pd.concat(dfs, ignore_index=True)

    event_features = parse_event(event_description)

    idade_media = df["idade"].mean()
    idade_min = df["idade"].min()
    idade_max = df["idade"].max()

    faculdade_top = (
        df["faculdade"]
        .dropna()
        .value_counts()
        .head(3)
        .index.tolist()
    )

    valor_medio = df["valor_medio"].mean()
    freq_media = df["freq_compra"].mean()

    texto = "Para esse tipo de evento, seu público ideal é composto por "

    if faculdade_top:
        texto += f"alunos de {', '.join(faculdade_top)}, "

    if pd.notnull(idade_media):
        texto += f"com idade média de {int(idade_media)} anos "

    if pd.notnull(idade_min) and pd.notnull(idade_max):
        texto += f"(variando entre {int(idade_min)} e {int(idade_max)} anos), "

    if pd.notnull(valor_medio):
        texto += f"com tickets médios em torno de R${int(valor_medio)}, "

    if pd.notnull(freq_media):
        texto += f"e frequência média de compra de {round(freq_media, 1)} eventos. "

    if "universitario" in event_description.lower():
        texto += "Esse perfil tem forte aderência a eventos universitários e sociais. "

    if "open bar" in event_description.lower():
        texto += "Eventos open bar tendem a performar melhor com esse público. "

    if "funk" in event_description.lower():
        texto += "Gêneros populares como funk aumentam o potencial de conversão. "

    return {
        "profile": texto
    }