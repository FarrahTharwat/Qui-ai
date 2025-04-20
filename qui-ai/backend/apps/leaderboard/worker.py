from Celery import celery_app
from database import redis_client, async_session_maker
from models import Leaderboard
from sqlalchemy.future import select
import asyncio


@celery_app.task
def update_leaderboard(scores):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(process_updates(scores))


async def process_updates(scores):
    async with async_session_maker() as db:
        for entry in scores:
            leaderboard_key = f"course_leaderboard:{entry['course_id']}"
            redis_client.zadd(leaderboard_key, {entry['username']: entry['score']})

            result = await db.execute(
                select(Leaderboard).filter_by(
                    course_id=entry['course_id'],
                    username=entry['username']
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.score = max(existing.score, entry['score'])
            else:
                db.add(Leaderboard(**entry))
        await db.commit()
