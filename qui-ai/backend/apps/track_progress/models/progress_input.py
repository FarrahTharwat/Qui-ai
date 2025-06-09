from pydantic import BaseModel

class ProgressInput(BaseModel):
    user_id: str
    lesson_id: str
    progress: int