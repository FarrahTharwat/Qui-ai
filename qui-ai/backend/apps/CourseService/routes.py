from fastapi import HTTPException, Depends, status, Query, APIRouter
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import requests
import json
import logging

from db_connection import get_db, verify_token
from models import (
    Course, Topic, Lesson,
    DifficultyLevel, LessonStatus,
    CourseCreate, CourseUpdate, CourseResponse, CourseStructureResponse,
    TopicCreate, TopicUpdate, TopicResponse, TopicWithLessonsResponse,
    LessonCreate, LessonUpdate, LessonResponse, LessonWithContentResponse
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI router
router = APIRouter(prefix="/api/course", tags=["Course-Service"])

# Helper function for model serialization
def serialize_course_response(course: Course) -> dict:
    """Convert Course ORM object to dictionary"""
    return CourseResponse.model_validate(course).model_dump()

def serialize_topic_response(topic: Topic) -> dict:
    """Convert Topic ORM object to dictionary"""
    topic_dict = TopicResponse.model_validate(topic).model_dump()
    topic_dict["prerequisites"] = json.loads(topic.prerequisites or "[]")
    return topic_dict

def serialize_lesson_response(lesson: Lesson) -> dict:
    """Convert Lesson ORM object to dictionary"""
    lesson_dict = LessonResponse.model_validate(lesson).model_dump()
    lesson_dict["prerequisites"] = json.loads(lesson.prerequisites or "[]")
    lesson_dict["learning_objectives"] = json.loads(lesson.learning_objectives or "[]")
    lesson_dict["key_concepts"] = json.loads(lesson.key_concepts or "[]")
    lesson_dict["examples"] = json.loads(lesson.examples or "[]")
    # Keep lesson_metadata as field name in serialization
    lesson_dict["lesson_metadata"] = json.loads(lesson.lesson_metadata or "{}")
    return lesson_dict

# Course endpoints
@router.post("/courses/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
        course: CourseCreate,
        db: Session = Depends(get_db),
        current_user: dict = Depends(verify_token)
):
    """Create a new course"""
    try:
        db_course = Course(**course.model_dump())
        db.add(db_course)
        db.commit()
        db.refresh(db_course)
        logger.info(f"Created course: {db_course.title} (ID: {db_course.id})")
        return db_course
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create course: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create course")

@router.get("/courses/", response_model=List[CourseResponse])
async def get_courses(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=100),
        difficulty: Optional[DifficultyLevel] = None,
        active_only: bool = Query(True),
        db: Session = Depends(get_db)
):
    """Get list of courses with optional filtering"""
    try:
        query = db.query(Course)

        if active_only:
            query = query.filter(Course.is_active == True)

        if difficulty:
            query = query.filter(Course.difficulty == difficulty)

        courses = query.offset(skip).limit(limit).all()
        return courses
    except Exception as e:
        logger.error(f"Failed to get courses: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve courses")

@router.get("/courses/{course_id}", response_model=CourseStructureResponse)
async def get_course(course_id: int, db: Session = Depends(get_db)):
    """Get course with its topics structure"""
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Load topics with the course
        topics = db.query(Topic).filter(
            Topic.course_id == course_id,
            Topic.is_active == True
        ).order_by(Topic.order_index).all()

        course_dict = serialize_course_response(course)
        course_dict["topics"] = [serialize_topic_response(topic) for topic in topics]

        return course_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get course {course_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve course")

@router.put("/courses/{course_id}", response_model=CourseResponse)
async def update_course(
        course_id: int,
        course_update: CourseUpdate,
        db: Session = Depends(get_db),
        current_user: dict = Depends(verify_token)
):
    """Update course information"""
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        update_data = course_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(course, field, value)

        db.commit()
        db.refresh(course)
        logger.info(f"Updated course: {course.title} (ID: {course.id})")
        return course
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update course {course_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update course")

# Topic endpoints
@router.post("/topics/", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(
        topic: TopicCreate,
        db: Session = Depends(get_db),
        current_user: dict = Depends(verify_token)
):
    """Create a new topic"""
    try:
        # Verify course exists
        course = db.query(Course).filter(Course.id == topic.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        topic_data = topic.model_dump()
        topic_data["prerequisites"] = json.dumps(topic_data.get("prerequisites", []))

        db_topic = Topic(**topic_data)
        db.add(db_topic)
        db.commit()
        db.refresh(db_topic)
        logger.info(f"Created topic: {db_topic.title} (ID: {db_topic.id})")
        return db_topic
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create topic: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create topic")

@router.get("/topics/{topic_id}", response_model=TopicWithLessonsResponse)
async def get_topic_with_lessons(topic_id: int, db: Session = Depends(get_db)):
    """Get topic with its lessons"""
    try:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        lessons = db.query(Lesson).filter(
            Lesson.topic_id == topic_id,
            Lesson.status == LessonStatus.PUBLISHED
        ).order_by(Lesson.order_index).all()

        topic_dict = serialize_topic_response(topic)
        topic_dict["lessons"] = [serialize_lesson_response(lesson) for lesson in lessons]

        return topic_dict
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get topic {topic_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve topic")

@router.put("/topics/{topic_id}", response_model=TopicResponse)
async def update_topic(
        topic_id: int,
        topic_update: TopicUpdate,
        db: Session = Depends(get_db),
        current_user: dict = Depends(verify_token)
):
    """Update topic information"""
    try:
        topic = db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        update_data = topic_update.model_dump(exclude_unset=True)
        if "prerequisites" in update_data:
            update_data["prerequisites"] = json.dumps(update_data["prerequisites"])

        for field, value in update_data.items():
            setattr(topic, field, value)

        db.commit()
        db.refresh(topic)
        logger.info(f"Updated topic: {topic.title} (ID: {topic.id})")
        return topic
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update topic {topic_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update topic")

# Lesson endpoints
@router.post("/lessons/", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
async def create_lesson(
        lesson: LessonCreate,
        db: Session = Depends(get_db),
        current_user: dict = Depends(verify_token)
):
    """Create a new lesson"""
    try:
        # Verify topic exists
        topic = db.query(Topic).filter(Topic.id == lesson.topic_id).first()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        lesson_data = lesson.model_dump()
        lesson_data["prerequisites"] = json.dumps(lesson_data.get("prerequisites", []))
        lesson_data["learning_objectives"] = json.dumps(lesson_data.get("learning_objectives", []))
        lesson_data["key_concepts"] = json.dumps(lesson_data.get("key_concepts", []))
        lesson_data["examples"] = json.dumps(lesson_data.get("examples", []))

        db_lesson = Lesson(**lesson_data)
        db.add(db_lesson)
        db.commit()
        db.refresh(db_lesson)

        # Send content to content_handler_service for processing
        try:
            await send_to_content_handler(db_lesson)
        except Exception as e:
            logger.warning(f"Failed to send lesson to content handler: {str(e)}")

        logger.info(f"Created lesson: {db_lesson.title} (ID: {db_lesson.id})")
        return db_lesson
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create lesson: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create lesson")

@router.get("/lessons/{lesson_id}", response_model=LessonWithContentResponse)
async def get_lesson(lesson_id: int, db: Session = Depends(get_db)):
    """Get lesson content for user consumption"""
    try:
        lesson = db.query(Lesson).filter(
            Lesson.id == lesson_id,
            Lesson.status == LessonStatus.PUBLISHED
        ).first()

        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found or not published")

        return serialize_lesson_response(lesson)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get lesson {lesson_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve lesson")

@router.put("/lessons/{lesson_id}", response_model=LessonResponse)
async def update_lesson(
        lesson_id: int,
        lesson_update: LessonUpdate,
        db: Session = Depends(get_db),
        current_user: dict = Depends(verify_token)
):
    """Update lesson information"""
    try:
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")

        update_data = lesson_update.model_dump(exclude_unset=True)

        # Handle JSON fields - Keep lesson_metadata as field name
        json_fields = ["prerequisites", "learning_objectives", "key_concepts", "examples", "lesson_metadata"]
        for field in json_fields:
            if field in update_data:
                update_data[field] = json.dumps(update_data[field])

        for field, value in update_data.items():
            setattr(lesson, field, value)

        db.commit()
        db.refresh(lesson)
        logger.info(f"Updated lesson: {lesson.title} (ID: {lesson.id})")
        return lesson
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update lesson {lesson_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update lesson")


@router.put("/lessons/{lesson_id}/publish")
async def publish_lesson(
        lesson_id: int,
        db: Session = Depends(get_db),
        current_user: dict = Depends(verify_token)
):
    """Publish a lesson to make it available to users"""
    try:
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")

        lesson.status = LessonStatus.PUBLISHED
        db.commit()

        logger.info(f"Published lesson: {lesson.title} (ID: {lesson.id})")
        return {"message": "Lesson published successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to publish lesson {lesson_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to publish lesson")

# Utility endpoints for microservice integration
@router.get("/courses/{course_id}/metadata")
async def get_course_metadata(course_id: int, db: Session = Depends(get_db)):
    """Get course metadata for other services (like recommendation service)"""
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        topics = db.query(Topic).filter(Topic.course_id == course_id).all()
        topic_count = len(topics)
        lesson_count = sum(len(topic.lessons) for topic in topics)

        return {
            "course_id": course.id,
            "title": course.title,
            "difficulty": course.difficulty,
            "topic_count": topic_count,
            "lesson_count": lesson_count,
            "estimated_duration_hours": course.estimated_duration_hours
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get course metadata {course_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve course metadata")

@router.get("/lessons/by-difficulty/{difficulty}")
async def get_lessons_by_difficulty(
        difficulty: DifficultyLevel,
        limit: int = Query(50, ge=1, le=100),
        db: Session = Depends(get_db)
):
    """Get lessons filtered by difficulty for recommendation service"""
    try:
        lessons = db.query(Lesson).filter(
            Lesson.difficulty == difficulty,
            Lesson.status == LessonStatus.PUBLISHED
        ).limit(limit).all()

        return [{"id": lesson.id, "title": lesson.title, "topic_id": lesson.topic_id} for lesson in lessons]
    except Exception as e:
        logger.error(f"Failed to get lessons by difficulty {difficulty}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve lessons")

# Health check
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "course_service"}

# Helper function to communicate with content_handler_service
async def send_to_content_handler(lesson: Lesson):
    """Send lesson content to content handler service for processing"""
    content_handler_url = os.getenv("CONTENT_HANDLER_URL", "http://localhost:8002")

    payload = {
        "lesson_id": lesson.id,
        "title": lesson.title,
        "content": lesson.content,
        "key_concepts": json.loads(lesson.key_concepts or "[]")
    }

    try:
        response = requests.post(
            f"{content_handler_url}/process-lesson",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        logger.info(f"Successfully sent lesson {lesson.id} to content handler")
    except requests.RequestException as e:
        logger.error(f"Failed to send lesson to content handler: {str(e)}")
        raise