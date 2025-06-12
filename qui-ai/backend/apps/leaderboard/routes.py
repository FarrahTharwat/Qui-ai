# Fixed routes.py
import asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, delete
from fastapi import APIRouter, HTTPException, Depends
from database import redis_client, LEADERBOARD_PREFIX, TRACKING_SERVICE_URL, get_db, sync_redis_with_postgresql
from models import Leaderboard, LeaderboardEntry
from typing import List
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Background sync task
sync_task = None


@router.on_event("startup")
async def start_sync_task():
    """Start background sync task (for FastAPI versions < 0.93.0)"""
    global sync_task
    if sync_task is None:
        logger.info("Starting background sync task...")
        sync_task = asyncio.create_task(sync_redis_with_postgresql())


@router.post("/submit_score/")
async def submit_score(entry: LeaderboardEntry, db: AsyncSession = Depends(get_db)):
    """Submit a single score"""
    try:
        if entry.score < 0:
            raise HTTPException(status_code=400, detail="Score must be non-negative")

        # Check for existing entry
        result = await db.execute(
            select(Leaderboard).where(
                and_(
                    Leaderboard.course_id == entry.course_id,
                    Leaderboard.username == entry.username
                )
            )
        )
        existing_entry = result.scalar_one_or_none()

        if existing_entry:
            # Update only if new score is higher
            if entry.score > existing_entry.score:
                existing_entry.score = entry.score
                logger.info(f"Updated score for {entry.username} in {entry.course_id}: {entry.score}")
            else:
                logger.info(
                    f"Score not updated for {entry.username} in {entry.course_id}: {entry.score} <= {existing_entry.score}")
        else:
            # Create new entry
            new_entry = Leaderboard(
                course_id=entry.course_id,
                username=entry.username,
                score=entry.score
            )
            db.add(new_entry)
            logger.info(f"Added new entry for {entry.username} in {entry.course_id}: {entry.score}")

        await db.commit()

        # Update Redis cache
        leaderboard_key = f"{LEADERBOARD_PREFIX}{entry.course_id}"
        redis_client.zadd(leaderboard_key, {entry.username: entry.score})

        return {
            "message": f"Score {entry.score} submitted for {entry.username} in course {entry.course_id}",
            "updated": True
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Error submitting score: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/submit_scores/")
async def submit_scores(entries: List[LeaderboardEntry], db: AsyncSession = Depends(get_db)):
    """Submit multiple scores"""
    try:
        if not entries:
            raise HTTPException(status_code=400, detail="No entries provided")

        updated_count = 0
        added_count = 0

        for entry in entries:
            if entry.score < 0:
                continue  # Skip invalid scores

            # Check for existing entry
            result = await db.execute(
                select(Leaderboard).where(
                    and_(
                        Leaderboard.course_id == entry.course_id,
                        Leaderboard.username == entry.username
                    )
                )
            )
            existing_entry = result.scalar_one_or_none()

            if existing_entry:
                if entry.score > existing_entry.score:
                    existing_entry.score = entry.score
                    updated_count += 1
            else:
                new_entry = Leaderboard(
                    course_id=entry.course_id,
                    username=entry.username,
                    score=entry.score
                )
                db.add(new_entry)
                added_count += 1

        await db.commit()

        # Update Redis cache for all entries
        with redis_client.pipeline() as pipe:
            for entry in entries:
                if entry.score >= 0:
                    leaderboard_key = f"{LEADERBOARD_PREFIX}{entry.course_id}"
                    pipe.zadd(leaderboard_key, {entry.username: entry.score})
            pipe.execute()

        return {
            "message": f"Successfully processed {len(entries)} entries",
            "updated": updated_count,
            "added": added_count,
            "total_processed": updated_count + added_count
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Error submitting scores: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rank/{course_id}/{username}")
async def get_user_rank(course_id: str, username: str):
    """Get user's rank in a course"""
    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"

    try:
        with redis_client.pipeline() as pipe:
            pipe.zscore(leaderboard_key, username)
            pipe.zrevrank(leaderboard_key, username)
            score, rank = pipe.execute()

        if score is None or rank is None:
            raise HTTPException(status_code=404, detail="User not found in this course")

        return {
            "username": username,
            "course_id": course_id,
            "rank": rank + 1,  # Convert to 1-based ranking
            "score": int(score)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user rank: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top/{course_id}")
@router.get("/top/{course_id}/{count}")
async def get_top_players(course_id: str, count: int = 10, db: AsyncSession = Depends(get_db)):
    """Get top players for a course"""
    if count <= 0:
        raise HTTPException(status_code=400, detail="Count must be positive")

    if count > 1000:  # Reasonable limit
        raise HTTPException(status_code=400, detail="Count cannot exceed 1000")

    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"

    try:
        # Try Redis first
        top_players = redis_client.zrevrange(leaderboard_key, 0, count - 1, withscores=True)

        if top_players:
            return [
                {
                    "rank": idx + 1,
                    "username": player[0],
                    "score": int(player[1])
                }
                for idx, player in enumerate(top_players)
            ]

        # Fallback to database
        result = await db.execute(
            select(Leaderboard)
            .where(Leaderboard.course_id == course_id)
            .order_by(Leaderboard.score.desc())
            .limit(count)
        )
        top_players = result.scalars().all()

        if not top_players:
            return []  # Return empty list instead of 404

        return [
            {
                "rank": idx + 1,
                "username": player.username,
                "score": player.score
            }
            for idx, player in enumerate(top_players)
        ]

    except Exception as e:
        logger.error(f"Error getting top players: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/courses/")
async def get_courses(db: AsyncSession = Depends(get_db)):
    """Get list of all courses with leaderboards"""
    try:
        result = await db.execute(
            select(Leaderboard.course_id).distinct()
        )
        courses = result.scalars().all()

        return {
            "courses": courses,
            "count": len(courses)
        }
    except Exception as e:
        logger.error(f"Error getting courses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fetch_and_update_leaderboard/")
async def fetch_and_update_leaderboard(db: AsyncSession = Depends(get_db)):
    """Fetch and update leaderboard from external service"""
    if not TRACKING_SERVICE_URL:
        raise HTTPException(status_code=500, detail="TRACKING_SERVICE_URL not configured")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(TRACKING_SERVICE_URL)
            response.raise_for_status()
            scores = response.json()

        if not isinstance(scores, list):
            raise HTTPException(status_code=400, detail="Expected list of scores from tracking service")

        # Process the scores directly
        updated_count = 0
        added_count = 0
        error_count = 0

        for score_data in scores:
            try:
                entry = LeaderboardEntry(**score_data)

                # Check existing entry
                result = await db.execute(
                    select(Leaderboard).where(
                        and_(
                            Leaderboard.course_id == entry.course_id,
                            Leaderboard.username == entry.username
                        )
                    )
                )
                existing_entry = result.scalar_one_or_none()

                if existing_entry:
                    if entry.score > existing_entry.score:
                        existing_entry.score = entry.score
                        updated_count += 1
                else:
                    new_entry = Leaderboard(
                        course_id=entry.course_id,
                        username=entry.username,
                        score=entry.score
                    )
                    db.add(new_entry)
                    added_count += 1

            except Exception as entry_error:
                logger.error(f"Error processing entry {score_data}: {entry_error}")
                error_count += 1
                continue

        await db.commit()

        # Update Redis cache
        with redis_client.pipeline() as pipe:
            for score_data in scores:
                try:
                    entry = LeaderboardEntry(**score_data)
                    leaderboard_key = f"{LEADERBOARD_PREFIX}{entry.course_id}"
                    pipe.zadd(leaderboard_key, {entry.username: entry.score})
                except:
                    continue
            pipe.execute()

        return {
            "message": f"Processed {len(scores)} entries",
            "updated": updated_count,
            "added": added_count,
            "errors": error_count,
            "total_processed": updated_count + added_count
        }

    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Error fetching scores: {str(e)}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/reset/{course_id}")
async def reset_leaderboard(course_id: str, db: AsyncSession = Depends(get_db)):
    """Reset leaderboard for a course"""
    try:
        # Count existing entries
        count_result = await db.execute(
            select(Leaderboard).where(Leaderboard.course_id == course_id)
        )
        entries = count_result.scalars().all()
        entry_count = len(entries)

        if entry_count == 0:
            raise HTTPException(status_code=404, detail="No leaderboard found for this course")

        # Delete from database
        await db.execute(
            delete(Leaderboard).where(Leaderboard.course_id == course_id)
        )
        await db.commit()

        # Delete from Redis
        leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
        redis_client.delete(leaderboard_key)

        return {
            "message": f"Leaderboard for course {course_id} reset successfully",
            "deleted_entries": entry_count
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error resetting leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{course_id}")
async def get_course_stats(course_id: str, db: AsyncSession = Depends(get_db)):
    """Get statistics for a course"""
    try:
        result = await db.execute(
            select(Leaderboard).where(Leaderboard.course_id == course_id)
        )
        entries = result.scalars().all()

        if not entries:
            raise HTTPException(status_code=404, detail="No data found for this course")

        scores = [entry.score for entry in entries]

        return {
            "course_id": course_id,
            "total_players": len(entries),
            "highest_score": max(scores),
            "lowest_score": min(scores),
            "average_score": sum(scores) / len(scores)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting course stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))