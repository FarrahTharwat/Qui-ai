from fastapi import FastAPI
from track_progress.routes import router

app = FastAPI()
app.include_router(router)
