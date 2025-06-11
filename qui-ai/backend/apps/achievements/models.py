from pydantic import BaseModel

class AchievementRequest(BaseModel):
    user_id: str
