from Celery import celery_app
from database import redis_client, get_database_url
from models import Leaderboard
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
import asyncio
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def update_leaderboard(self, scores):
    """
    Celery task to update leaderboard data
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(process_updates(scores))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Leaderboard update failed: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


async def process_updates(scores):
    """
    Process leaderboard updates asynchronously
    """
    # Create a new database session for this task
    database_url = get_database_url()
    engine = create_async_engine(database_url)
    session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    updated_count = 0

    try:
        async with session_maker() as db:
            for entry in scores:
                try:
                    course_id = entry['course_id']
                    username = entry['username']
                    score = entry['score']

                    # Update Redis immediately
                    leaderboard_key = f"course_leaderboard:{course_id}"
                    redis_client.zadd(leaderboard_key, {username: score})

                    # Check if entry exists in database
                    result = await db.execute(
                        select(Leaderboard).filter_by(
                            course_id=course_id,
                            username=username
                        )
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        # Update only if new score is higher
                        if score > existing.score:
                            existing.score = score
                            logger.info(f"Updated score for {username} in {course_id}: {score}")
                    else:
                        # Create new entry
                        new_entry = Leaderboard(
                            course_id=course_id,
                            username=username,
                            score=score
                        )
                        db.add(new_entry)
                        logger.info(f"Added new entry for {username} in {course_id}: {score}")

                    updated_count += 1

                except Exception as entry_error:
                    logger.error(f"Failed to process entry {entry}: {entry_error}")
                    continue

            # Commit all changes
            await db.commit()
            logger.info(f"Successfully processed {updated_count} leaderboard updates")

    except Exception as db_error:
        logger.error(f"Database operation failed: {db_error}")
        raise
    finally:
        await engine.dispose()

    return {
        "processed": len(scores),
        "updated": updated_count,
        "status": "success"
    }


@celery_app.task
def sync_leaderboard_cache():
    """
    Task to sync database data to Redis cache
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(sync_cache_data())
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Cache sync failed: {e}")
        raise


async def sync_cache_data():
    """
    Sync all leaderboard data from database to Redis
    """
    database_url = get_database_url()
    engine = create_async_engine(database_url)
    session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_maker() as db:
            result = await db.execute(select(Leaderboard))
            entries = result.scalars().all()

            # Group entries by course_id for efficient Redis operations
            course_data = {}
            for entry in entries:
                if entry.course_id not in course_data:
                    course_data[entry.course_id] = {}
                course_data[entry.course_id][entry.username] = entry.score

            # Update Redis with pipeline for efficiency
            with redis_client.pipeline() as pipe:
                for course_id, user_scores in course_data.items():
                    leaderboard_key = f"course_leaderboard:{course_id}"
                    pipe.delete(leaderboard_key)  # Clear existing data
                    pipe.zadd(leaderboard_key, user_scores)
                pipe.execute()

            logger.info(f"Synced {len(entries)} entries across {len(course_data)} courses")
            return {"synced_entries": len(entries), "courses": len(course_data)}

    except Exception as e:
        logger.error(f"Cache sync error: {e}")
        raise
    finally:
        await engine.dispose()