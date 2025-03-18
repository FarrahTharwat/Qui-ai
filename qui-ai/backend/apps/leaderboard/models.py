from pydantic import BaseModel

class LeaderboardEntry(BaseModel):
    course_id: str
    username: str
    score: int