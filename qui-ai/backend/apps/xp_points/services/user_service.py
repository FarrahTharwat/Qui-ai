from pydantic import BaseModel

class UserInfo(BaseModel):
    user_id: str
    name: str
    email: str

async def get_user_info(user_id: str):
    return UserInfo(user_id=user_id, name="Mock User", email="mock@example.com")