from pydantic import BaseModel
from typing import List

class UserStats(BaseModel):
    user_id: str
    # Accepts any dynamic key (xp, streaks, etc.)
    # So you can do: UserStats(user_id="123", xp=1000, quizzes_passed=5)
    class Config:
        extra = "allow"

class Achievement(BaseModel):
    name: str
    description: str
    condition_type: str  # dynamic field name (like "xp" or "streak_days")
    condition_value: int


