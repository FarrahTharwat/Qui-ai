from pydantic import BaseModel

class AchievementInput(BaseModel):
    user_id: str
    xp: int