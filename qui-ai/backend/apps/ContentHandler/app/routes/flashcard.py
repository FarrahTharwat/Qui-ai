from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from model.flashcard import Flashcard  # Absolute import
from app.utils.db import get_db  # Absolute import

router = APIRouter()

@router.get("/flashcards")
def get_flashcards(db: Session = Depends(get_db)):
    return db.query(Flashcard).all()