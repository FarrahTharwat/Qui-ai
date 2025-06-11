from pydantic import BaseModel
from typing import Literal

class Progress(BaseModel):
    user_id: str
    activity_type: Literal["lesson", "quiz", "streak"]
    activity_id: str
    status: Literal["not_started", "in_progress", "completed"]
