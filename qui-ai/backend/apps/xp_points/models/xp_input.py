from pydantic import BaseModel

class XPInput(BaseModel):
    user_id: str
    activity_type: str
    amount: int