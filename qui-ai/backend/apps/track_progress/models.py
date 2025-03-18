from pydantic import BaseModel

class ProgressRequest(BaseModel):
    user_id: str
    lesson_id: str
    xp_gained: int
