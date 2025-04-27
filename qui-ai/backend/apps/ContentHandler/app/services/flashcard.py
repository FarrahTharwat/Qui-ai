from sqlalchemy.orm import Session
from ContentHandler.model.flashcard import Flashcard

class FlashcardService:
    @staticmethod
    def get_flashcards(db: Session):
        return db.query(Flashcard).all()