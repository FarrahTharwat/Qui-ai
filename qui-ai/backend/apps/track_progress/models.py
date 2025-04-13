from pydantic import BaseModel
from typing import Optional

class TrackRequest(BaseModel):
    user_id: str
    activity_id: str
    activity_type: str  # e.g., lesson, quiz, video
    metadata: Optional[dict] = None  # Optional extra info


