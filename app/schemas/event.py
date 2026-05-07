from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class EventCreate(BaseModel):
    client_id: str
    description: str


class EventOut(BaseModel):
    id: int
    client_id: str
    description: str
    file_name: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}