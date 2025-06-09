from fastapi import FastAPI
from routes.progress_routes import router
from database import db

app = FastAPI()

@app.on_event("startup")
async def connect():
    app.mongodb = db

@app.on_event("shutdown")
async def disconnect():
    app.mongodb = None

app.include_router(router)