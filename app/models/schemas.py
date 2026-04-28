from pydantic import BaseModel

class EventRequest(BaseModel):
    description: str