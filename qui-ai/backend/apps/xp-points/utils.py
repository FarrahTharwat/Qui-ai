# ================== utils.py ==================
import httpx

async def notify_xp_service(user_id: str, activity_type: str):
    async with httpx.AsyncClient() as client:
        response = await client.post("http://localhost:8001/xp/add_xp/", json={
            "user_id": user_id,
            "activity_type": activity_type
        })
        return response.json()