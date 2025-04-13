from pydantic import BaseModel
from typing import Optional

class XPRequest(BaseModel):
    user_id: str
    activity_type: str  # e.g., "lesson", "quiz", "custom"
    amount: Optional[int] = None  # used only for custom



