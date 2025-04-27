from fastapi import FastAPI
from app.utils.db import SessionLocal, Base, engine, get_db
from model.flashcard import Flashcard

app = FastAPI()
app.include_router(Flashcard.router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Welcome to ContentHandler API!"}

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
