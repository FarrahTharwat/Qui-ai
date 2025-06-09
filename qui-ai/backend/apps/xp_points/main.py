from fastapi import FastAPI
from routes.xp_routes import router
from database import db

app = FastAPI()

@app.on_event("startup")
async def startup():
    app.mongodb = db

@app.on_event("shutdown")
async def shutdown():
    app.mongodb = None

app.include_router(router)