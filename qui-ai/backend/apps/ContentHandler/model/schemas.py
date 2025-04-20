# model/schemas.py
from pydantic import BaseModel

class Document(BaseModel):
    title: str
    content: str
    flashcards: list
