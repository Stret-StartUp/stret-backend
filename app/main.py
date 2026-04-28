from fastapi import FastAPI
from app.routes.process import router as process_router
from app.routes.upload import router as upload_router
from app.routes.query import router as query_router
from app.routes.profile import router as profile_router

app = FastAPI(title="Event AI Backend")

app.include_router(profile_router)
app.include_router(upload_router)
app.include_router(query_router)