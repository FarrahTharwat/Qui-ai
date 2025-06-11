from fastapi import HTTPException, Depends, status, Query, APIRouter
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import logging
from datetime import datetime

from db_connection import get_db, verify_token
from models import (
    Course, Topic, Lesson,
    DifficultyLevel, LessonStatus,
    CourseCreate, CourseUpdate, CourseResponse, CourseStructureResponse,
    TopicCreate, TopicUpdate, TopicResponse, TopicWithLessonsResponse,
    LessonCreate, LessonUpdate, LessonResponse, LessonWithContentResponse, MCQ, MCQUserAnswer, QuestionType,
    MCQCreate, MCQUpdate, MCQResponse, MCQWithAnswersResponse,
    MCQSubmitAnswer, MCQAnswerResponse, MCQUserAnswerResponse,
    LessonMCQsResponse, MCQStatistics, MCQOption
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI router
router = APIRouter(prefix="/api/course", tags=["Course-Service"])


# Helper functions for safe JSON handling
def safe_json_loads(json_str, default=None):
    """Safely parse JSON string with fallback to default value"""
    if json_str is None:
        return default or []

    if isinstance(json_str, (list, dict)):
        return json_str

    try:
        cleaned_str = ''.join(char for char in json_str if ord(char) >= 32 or char in '\t\n\r')
        return json.loads(cleaned_str)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning(f"Failed to parse JSON: {json_str[:100]}... Error: {str(e)}")
        return default or []


def safe_json_dumps(data):
    """Safely convert data to JSON string"""
    if data is None:
        return "[]"

    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            return json.dumps(parsed, ensure_ascii=False)
        except:
            return json.dumps([data], ensure_ascii=False)

    try:
        return json.dumps(data, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        logger.warning(f"Failed to serialize to JSON: {data}. Error: {str(e)}")
        return "[]"


def serialize_topic_response(topic: Topic) -> dict:
    """Convert Topic ORM object to dictionary with safe JSON handling"""
    try:
        topic_dict = {
            "id": topic.id,
            "title": topic.title,
            "description": topic.description,
            "course_id": topic.course_id,
            "order_index": topic.order_index,
            "difficulty": topic.difficulty,
            "prerequisites": safe_json_loads(topic.prerequisites, []),
            "estimated_duration_minutes": topic.estimated_duration_minutes,
            "is_active": topic.is_active,
            "created_at": topic.created_at,
            "updated_at": topic.updated_at
        }
        return TopicResponse.model_validate(topic_dict).model_dump()
    except Exception as e:
        logger.error(f"Error serializing topic {topic.id}: {str(e)}")
        return TopicResponse.model_validate(topic).model_dump()


def serialize_lesson_response(lesson: Lesson) -> dict:
    """Convert Lesson ORM object to dictionary with safe JSON handling"""
    try:
        lesson_dict = {
            "id": lesson.id,
            "title": lesson.title,
            "content": lesson.content,
            "topic_id": lesson.topic_id,
            "lesson_type": lesson.lesson_type,
            "difficulty": lesson.difficulty,
            "order_index": lesson.order_index,
            "prerequisites": safe_json_loads(lesson.prerequisites, []),
            "learning_objectives": safe_json_loads(lesson.learning_objectives, []),
            "key_concepts": safe_json_loads(lesson.key_concepts, []),
            "examples": safe_json_loads(lesson.examples, []),
            "estimated_duration_minutes": lesson.estimated_duration_minutes,
            "xp_reward": lesson.xp_reward,
            "status": lesson.status,
            "lesson_metadata": safe_json_loads(lesson.lesson_metadata, {}),
            "created_at": lesson.created_at,
            "updated_at": lesson.updated_at
        }
        return LessonResponse.model_validate(lesson_dict).model_dump()
    except Exception as e:
        logger.error(f"Error serializing lesson {lesson.id}: {str(e)}")
        return LessonResponse.model_validate(lesson).model_dump()


def serialize_mcq_response(mcq: MCQ, include_answers: bool = False) -> dict:
    """Convert MCQ ORM object to dictionary with safe JSON handling"""
    try:
        mcq_dict = {
            "id": mcq.id,
            "lesson_id": mcq.lesson_id,
            "question": mcq.question,
            "question_type": mcq.question_type,
            "options": safe_json_loads(mcq.options, []),
            "difficulty": mcq.difficulty,
            "order_index": mcq.order_index,
            "points": mcq.points,
            "time_limit_seconds": mcq.time_limit_seconds,
            "hints": safe_json_loads(mcq.hints, []),
            "tags": safe_json_loads(mcq.tags, []),
            "is_active": mcq.is_active,
            "created_at": mcq.created_at,
            "updated_at": mcq.updated_at
        }

        if include_answers:
            mcq_dict["correct_answers"] = safe_json_loads(mcq.correct_answers, [])
            mcq_dict["explanation"] = mcq.explanation
            return MCQWithAnswersResponse.model_validate(mcq_dict).model_dump()

        return MCQResponse.model_validate(mcq_dict).model_dump()
    except Exception as e:
        logger.error(f"Error serializing MCQ {mcq.id}: {str(e)}")
        base_response = MCQWithAnswersResponse if include_answers else MCQResponse
        return base_response.model_validate(mcq).model_dump()


# MCQ Endpoints - Add these after your existing lesson endpoints

@router.post("/mcqs/", response_model=MCQWithAnswersResponse, status_code=status.HTTP_201_CREATED)
async def create_mcq(
        mcq: MCQCreate,
        db: Session = Depends(get_db),
        current_user: dict = Depends(verify_token)
):
    """Create a new MCQ for a lesson"""
    try:
        # Verify lesson exists
        lesson = db.query(Lesson).filter(Lesson.id == mcq.lesson_id).first()
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")

        # Validate correct answers indices
        if not mcq.correct_answers or max(mcq.correct_answers) >= len(mcq.options):
            raise HTTPException(status_code=400, detail="Invalid correct answer indices")

        # Validate question type constraints
        if mcq.question_type == QuestionType.SINGLE_CHOICE and len(mcq.correct_answers) > 1:
            raise HTTPException(status_code=400, detail="Single choice questions can only have one correct answer")

        if mcq.question_type == QuestionType.TRUE_FALSE and len(mcq.options) != 2:
            raise HTTPException(status_code=400, detail="True/False questions must have exactly 2 options")

        # Prepare data for database
        mcq_data = mcq.model_dump()
        mcq_data["options"] = safe_json_dumps([opt.model_dump() for opt in mcq.options])
        mcq_data["correct_answers"] = safe_json_dumps(mcq.correct_answers)
        mcq_data["hints"] = safe_json_dumps(mcq.hints or [])
        mcq_data["tags"] = safe_json_dumps(mcq.tags or [])

        # Handle enum values
        if hasattr(mcq_data["question_type"], 'value'):
            mcq_data["question_type"] = mcq_data["question_type"].value
        if hasattr(mcq_data["difficulty"], 'value'):
            mcq_data["difficulty"] = mcq_data["difficulty"].value

        db_mcq = MCQ(**mcq_data)
        db.add(db_mcq)
        db.commit()
        db.refresh(db_mcq)

        logger.info(f"Created MCQ for lesson {mcq.lesson_id} (MCQ ID: {db_mcq.id})")
        return serialize_mcq_response(db_mcq, include_answers=True)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create MCQ: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create MCQ")

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

        topics = db.query(Topic).filter(
            Topic.course_id == course_id
        ).order_by(Topic.order_index).all()

        course_dict = CourseResponse.model_validate(course).model_dump()
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
        course = db.query(Course).filter(Course.id == topic.course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        topic_data = topic.model_dump()
        topic_data["prerequisites"] = safe_json_dumps(topic_data.get("prerequisites", []))

        if hasattr(topic_data["difficulty"], 'value'):
            topic_data["difficulty"] = topic_data["difficulty"].value

        db_topic = Topic(**topic_data)
        db.add(db_topic)
        db.commit()
        db.refresh(db_topic)

        logger.info(f"Created topic: {db_topic.title} (ID: {db_topic.id})")
        return serialize_topic_response(db_topic)
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
            Lesson.status == LessonStatus.PUBLISHED.value
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
            update_data["prerequisites"] = safe_json_dumps(update_data["prerequisites"])

        if "difficulty" in update_data and hasattr(update_data["difficulty"], 'value'):
            update_data["difficulty"] = update_data["difficulty"].value

        for field, value in update_data.items():
            setattr(topic, field, value)

        db.commit()
        db.refresh(topic)
        logger.info(f"Updated topic: {topic.title} (ID: {topic.id})")
        return serialize_topic_response(topic)
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
        topic = db.query(Topic).filter(Topic.id == lesson.topic_id).first()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        lesson_data = lesson.model_dump()

        # Convert list fields to JSON strings
        json_fields = ["prerequisites", "learning_objectives", "key_concepts", "examples"]
        for field in json_fields:
            lesson_data[field] = safe_json_dumps(lesson_data.get(field, []))

        # Convert enums to string values
        if hasattr(lesson_data["lesson_type"], 'value'):
            lesson_data["lesson_type"] = lesson_data["lesson_type"].value
        if hasattr(lesson_data["difficulty"], 'value'):
            lesson_data["difficulty"] = lesson_data["difficulty"].value

        db_lesson = Lesson(**lesson_data)
        db.add(db_lesson)
        db.commit()
        db.refresh(db_lesson)

        logger.info(f"Created lesson: {db_lesson.title} (ID: {db_lesson.id})")
        return serialize_lesson_response(db_lesson)
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
            Lesson.status == LessonStatus.PUBLISHED.value
        ).first()

        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found or not published")

        lesson_dict = {
            "id": lesson.id,
            "title": lesson.title,
            "content": lesson.content,
            "topic_id": lesson.topic_id,
            "lesson_type": lesson.lesson_type,
            "difficulty": lesson.difficulty,
            "order_index": lesson.order_index,
            "prerequisites": safe_json_loads(lesson.prerequisites, []),
            "learning_objectives": safe_json_loads(lesson.learning_objectives, []),
            "key_concepts": safe_json_loads(lesson.key_concepts, []),
            "examples": safe_json_loads(lesson.examples, []),
            "estimated_duration_minutes": lesson.estimated_duration_minutes,
            "xp_reward": lesson.xp_reward,
            "status": lesson.status,
            "lesson_metadata": safe_json_loads(lesson.lesson_metadata, {}),
            "created_at": lesson.created_at,
            "updated_at": lesson.updated_at
        }

        return LessonWithContentResponse.model_validate(lesson_dict)
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

        # Handle JSON fields
        json_fields = ["prerequisites", "learning_objectives", "key_concepts", "examples", "lesson_metadata"]
        for field in json_fields:
            if field in update_data:
                update_data[field] = safe_json_dumps(update_data[field])

        # Handle enum fields
        enum_fields = ["lesson_type", "difficulty", "status"]
        for field in enum_fields:
            if field in update_data and hasattr(update_data[field], 'value'):
                update_data[field] = update_data[field].value

        for field, value in update_data.items():
            setattr(lesson, field, value)

        db.commit()
        db.refresh(lesson)
        logger.info(f"Updated lesson: {lesson.title} (ID: {lesson.id})")
        return serialize_lesson_response(lesson)
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

        lesson.status = LessonStatus.PUBLISHED.value
        db.commit()

        logger.info(f"Published lesson: {lesson.title} (ID: {lesson.id})")
        return {"message": "Lesson published successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to publish lesson {lesson_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to publish lesson")


# Navigation endpoints
# Replace the navigation endpoints in your routes.py with these fixed versions

@router.get("/lessons/{lesson_id}/next")
async def get_next_lesson(lesson_id: int, db: Session = Depends(get_db)):
    """Get the next lesson ID for sequential navigation"""
    try:
        current_lesson = db.query(Lesson).filter(
            Lesson.id == lesson_id,
            Lesson.status == LessonStatus.PUBLISHED.value
        ).first()

        if not current_lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")

        topic = db.query(Topic).filter(Topic.id == current_lesson.topic_id).first()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        # Try next lesson in same topic
        next_lesson = db.query(Lesson).filter(
            Lesson.topic_id == current_lesson.topic_id,
            Lesson.order_index > current_lesson.order_index,
            Lesson.status == LessonStatus.PUBLISHED.value
        ).order_by(Lesson.order_index).first()

        # If no next lesson in topic, get first lesson of next topic
        if not next_lesson:
            next_topic = db.query(Topic).filter(
                Topic.course_id == topic.course_id,
                Topic.order_index > topic.order_index
                # Removed is_active check since your Topic model doesn't have it
            ).order_by(Topic.order_index).first()

            if next_topic:
                next_lesson = db.query(Lesson).filter(
                    Lesson.topic_id == next_topic.id,
                    Lesson.status == LessonStatus.PUBLISHED.value
                ).order_by(Lesson.order_index).first()

        if next_lesson:
            return {
                "next_lesson_id": next_lesson.id,
                "title": next_lesson.title,
                "topic_id": next_lesson.topic_id
            }
        else:
            return {"next_lesson_id": None, "message": "No more lessons available"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get next lesson for {lesson_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get next lesson")


@router.get("/lessons/{lesson_id}/previous")
async def get_previous_lesson(lesson_id: int, db: Session = Depends(get_db)):
    """Get the previous lesson ID for sequential navigation"""
    try:
        current_lesson = db.query(Lesson).filter(
            Lesson.id == lesson_id,
            Lesson.status == LessonStatus.PUBLISHED.value
        ).first()

        if not current_lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")

        topic = db.query(Topic).filter(Topic.id == current_lesson.topic_id).first()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

        # Try previous lesson in same topic
        previous_lesson = db.query(Lesson).filter(
            Lesson.topic_id == current_lesson.topic_id,
            Lesson.order_index < current_lesson.order_index,
            Lesson.status == LessonStatus.PUBLISHED.value
        ).order_by(Lesson.order_index.desc()).first()

        # If no previous lesson in topic, get last lesson of previous topic
        if not previous_lesson:
            previous_topic = db.query(Topic).filter(
                Topic.course_id == topic.course_id,
                Topic.order_index < topic.order_index
                # Removed is_active check since your Topic model doesn't have it
            ).order_by(Topic.order_index.desc()).first()

            if previous_topic:
                previous_lesson = db.query(Lesson).filter(
                    Lesson.topic_id == previous_topic.id,
                    Lesson.status == LessonStatus.PUBLISHED.value
                ).order_by(Lesson.order_index.desc()).first()

        if previous_lesson:
            return {
                "previous_lesson_id": previous_lesson.id,
                "title": previous_lesson.title,
                "topic_id": previous_lesson.topic_id
            }
        else:
            return {"previous_lesson_id": None, "message": "No previous lessons available"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get previous lesson for {lesson_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get previous lesson")

# Utility endpoints
@router.get("/courses/{course_id}/metadata")
async def get_course_metadata(course_id: int, db: Session = Depends(get_db)):
    """Get course metadata for other services"""
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        topics = db.query(Topic).filter(Topic.course_id == course_id).all()
        topic_count = len(topics)

        # Count lessons across all topics
        lesson_count = 0
        for topic in topics:
            topic_lessons = db.query(Lesson).filter(Lesson.topic_id == topic.id).count()
            lesson_count += topic_lessons

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
    """Get lessons filtered by difficulty"""
    try:
        lessons = db.query(Lesson).filter(
            Lesson.difficulty == difficulty.value,
            Lesson.status == LessonStatus.PUBLISHED.value
        ).limit(limit).all()

        return [{"id": lesson.id, "title": lesson.title, "topic_id": lesson.topic_id} for lesson in lessons]
    except Exception as e:
        logger.error(f"Failed to get lessons by difficulty {difficulty}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve lessons")


# Add this endpoint to your router - it was missing from the original code

@router.post("/lessons/{lesson_id}/mcqs", response_model=MCQWithAnswersResponse, status_code=status.HTTP_201_CREATED)
async def create_mcq(
        lesson_id: int,
        mcq: MCQCreate,
        db: Session = Depends(get_db)
):
    """Create a new MCQ for a specific lesson"""
    try:
        # Verify lesson exists
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")

        # Ensure lesson_id matches
        mcq.lesson_id = lesson_id

        # Validate correct answers indices
        if not mcq.correct_answers or max(mcq.correct_answers) >= len(mcq.options):
            raise HTTPException(status_code=400, detail="Invalid correct answer indices")

        # Prepare data for database
        mcq_dict = mcq.model_dump()
        mcq_dict["options"] = safe_json_dumps([opt.model_dump() for opt in mcq.options])
        mcq_dict["correct_answers"] = safe_json_dumps(mcq.correct_answers)
        mcq_dict["hints"] = safe_json_dumps(mcq.hints or [])
        mcq_dict["tags"] = safe_json_dumps(mcq.tags or [])

        # Handle enum fields
        if hasattr(mcq_dict["question_type"], 'value'):
            mcq_dict["question_type"] = mcq_dict["question_type"].value
        if hasattr(mcq_dict["difficulty"], 'value'):
            mcq_dict["difficulty"] = mcq_dict["difficulty"].value

        # Create MCQ
        db_mcq = MCQ(**mcq_dict)
        db.add(db_mcq)
        db.commit()
        db.refresh(db_mcq)

        logger.info(f"Created MCQ {db_mcq.id} for lesson {lesson_id}")
        return serialize_mcq_response(db_mcq, include_answers=True)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create MCQ for lesson {lesson_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create MCQ")
@router.get("/lessons/{lesson_id}/mcqs", response_model=LessonMCQsResponse)
async def get_lesson_mcqs(
        lesson_id: int,
        include_answers: bool = Query(False, description="Include correct answers for testing"),
        db: Session = Depends(get_db)
):
    """Get all MCQs for a specific lesson"""
    try:
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")

        # For testing, allow answers to be included with parameter
        show_answers = include_answers

        mcqs = db.query(MCQ).filter(
            MCQ.lesson_id == lesson_id,
            MCQ.is_active == True
        ).order_by(MCQ.order_index).all()

        mcqs_data = [serialize_mcq_response(mcq, include_answers=show_answers) for mcq in mcqs]
        total_points = sum(mcq.points for mcq in mcqs)

        return {
            "lesson_id": lesson_id,
            "lesson_title": lesson.title,
            "mcqs": mcqs_data,
            "total_mcqs": len(mcqs),
            "total_points": total_points
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCQs for lesson {lesson_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve MCQs")


@router.get("/mcqs/{mcq_id}", response_model=MCQResponse)
async def get_mcq(mcq_id: int, db: Session = Depends(get_db)):
    """Get a specific MCQ (without answers for students)"""
    try:
        mcq = db.query(MCQ).filter(
            MCQ.id == mcq_id,
            MCQ.is_active == True
        ).first()

        if not mcq:
            raise HTTPException(status_code=404, detail="MCQ not found")

        return serialize_mcq_response(mcq, include_answers=False)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCQ {mcq_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve MCQ")


@router.put("/mcqs/{mcq_id}", response_model=MCQWithAnswersResponse)
async def update_mcq(
        mcq_id: int,
        mcq_update: MCQUpdate,
        db: Session = Depends(get_db)
):
    """Update an existing MCQ"""
    try:
        mcq = db.query(MCQ).filter(MCQ.id == mcq_id).first()
        if not mcq:
            raise HTTPException(status_code=404, detail="MCQ not found")

        update_data = mcq_update.model_dump(exclude_unset=True)

        # Validate if updating options and correct answers
        if "options" in update_data and "correct_answers" in update_data:
            if max(update_data["correct_answers"]) >= len(update_data["options"]):
                raise HTTPException(status_code=400, detail="Invalid correct answer indices")

        # Handle JSON fields
        if "options" in update_data:
            update_data["options"] = safe_json_dumps([opt.model_dump() for opt in update_data["options"]])
        if "correct_answers" in update_data:
            update_data["correct_answers"] = safe_json_dumps(update_data["correct_answers"])
        if "hints" in update_data:
            update_data["hints"] = safe_json_dumps(update_data["hints"])
        if "tags" in update_data:
            update_data["tags"] = safe_json_dumps(update_data["tags"])

        # Handle enum fields
        enum_fields = ["question_type", "difficulty"]
        for field in enum_fields:
            if field in update_data and hasattr(update_data[field], 'value'):
                update_data[field] = update_data[field].value

        for field, value in update_data.items():
            setattr(mcq, field, value)

        db.commit()
        db.refresh(mcq)

        logger.info(f"Updated MCQ {mcq_id}")
        return serialize_mcq_response(mcq, include_answers=True)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update MCQ {mcq_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update MCQ")


@router.delete("/mcqs/{mcq_id}")
async def delete_mcq(
        mcq_id: int,
        db: Session = Depends(get_db)
):
    """Soft delete an MCQ (set is_active to False)"""
    try:
        mcq = db.query(MCQ).filter(MCQ.id == mcq_id).first()
        if not mcq:
            raise HTTPException(status_code=404, detail="MCQ not found")

        mcq.is_active = False
        db.commit()

        logger.info(f"Deleted MCQ {mcq_id}")
        return {"message": "MCQ deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete MCQ {mcq_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete MCQ")


# Student MCQ Interaction Endpoints

@router.post("/mcqs/{mcq_id}/submit", response_model=MCQAnswerResponse)
async def submit_mcq_answer(
        mcq_id: int,
        answer: MCQSubmitAnswer,
        user_id: int = Query(..., description="User ID for testing"),
        db: Session = Depends(get_db)
):
    """Submit an answer to an MCQ"""
    try:
        mcq = db.query(MCQ).filter(
            MCQ.id == mcq_id,
            MCQ.is_active == True
        ).first()

        if not mcq:
            raise HTTPException(status_code=404, detail="MCQ not found")

        correct_answers = safe_json_loads(mcq.correct_answers, [])

        # Check if answer is correct
        is_correct = sorted(answer.selected_answers) == sorted(correct_answers)
        points_earned = mcq.points if is_correct else 0

        # Check if user has already answered this MCQ
        existing_answer = db.query(MCQUserAnswer).filter(
            MCQUserAnswer.user_id == user_id,
            MCQUserAnswer.mcq_id == mcq_id
        ).first()

        if existing_answer:
            # Update existing answer
            existing_answer.selected_answers = safe_json_dumps(answer.selected_answers)
            existing_answer.is_correct = is_correct
            existing_answer.points_earned = points_earned
            existing_answer.time_taken_seconds = answer.time_taken_seconds
            existing_answer.attempts_count += 1
            existing_answer.answered_at = datetime.utcnow()
        else:
            # Create new answer record
            user_answer = MCQUserAnswer(
                user_id=user_id,
                mcq_id=mcq_id,
                lesson_id=mcq.lesson_id,
                selected_answers=safe_json_dumps(answer.selected_answers),
                is_correct=is_correct,
                points_earned=points_earned,
                time_taken_seconds=answer.time_taken_seconds,
                attempts_count=1
            )
            db.add(user_answer)

        db.commit()

        logger.info(f"User {user_id} answered MCQ {mcq_id}, correct: {is_correct}")

        return {
            "mcq_id": mcq_id,
            "is_correct": is_correct,
            "correct_answers": correct_answers,
            "explanation": mcq.explanation,
            "points_earned": points_earned,
            "time_taken_seconds": answer.time_taken_seconds
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to submit MCQ answer: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit answer")


@router.get("/lessons/{lesson_id}/mcqs/progress")
async def get_lesson_mcq_progress(
        lesson_id: int,
        user_id: int = Query(..., description="User ID for testing"),
        db: Session = Depends(get_db)
):
    """Get user's progress on lesson MCQs"""
    try:
        # Get all MCQs for the lesson
        mcqs = db.query(MCQ).filter(
            MCQ.lesson_id == lesson_id,
            MCQ.is_active == True
        ).all()

        # Get user's answers
        user_answers = db.query(MCQUserAnswer).filter(
            MCQUserAnswer.user_id == user_id,
            MCQUserAnswer.lesson_id == lesson_id
        ).all()

        answer_dict = {ans.mcq_id: ans for ans in user_answers}

        progress = []
        total_points = 0
        earned_points = 0

        for mcq in mcqs:
            total_points += mcq.points
            user_answer = answer_dict.get(mcq.id)

            mcq_progress = {
                "mcq_id": mcq.id,
                "question": mcq.question[:100] + "..." if len(mcq.question) > 100 else mcq.question,
                "points": mcq.points,
                "answered": user_answer is not None,
                "is_correct": user_answer.is_correct if user_answer else False,
                "points_earned": user_answer.points_earned if user_answer else 0,
                "attempts": user_answer.attempts_count if user_answer else 0
            }

            if user_answer:
                earned_points += user_answer.points_earned

            progress.append(mcq_progress)

        completion_rate = (len([p for p in progress if p["answered"]]) / len(progress)) * 100 if progress else 0
        success_rate = (len([p for p in progress if p["is_correct"]]) / len(
            [p for p in progress if p["answered"]])) * 100 if any(p["answered"] for p in progress) else 0

        return {
            "lesson_id": lesson_id,
            "total_mcqs": len(mcqs),
            "answered_mcqs": len([p for p in progress if p["answered"]]),
            "correct_answers": len([p for p in progress if p["is_correct"]]),
            "total_points": total_points,
            "earned_points": earned_points,
            "completion_rate": round(completion_rate, 2),
            "success_rate": round(success_rate, 2),
            "mcq_progress": progress
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCQ progress for lesson {lesson_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get MCQ progress")


# Admin/Analytics Endpoints

@router.get("/mcqs/{mcq_id}/statistics", response_model=MCQStatistics)
async def get_mcq_statistics(
        mcq_id: int,
        db: Session = Depends(get_db)
):
    """Get statistics for a specific MCQ"""
    try:
        mcq = db.query(MCQ).filter(MCQ.id == mcq_id).first()
        if not mcq:
            raise HTTPException(status_code=404, detail="MCQ not found")

        # Get all user answers for this MCQ
        user_answers = db.query(MCQUserAnswer).filter(MCQUserAnswer.mcq_id == mcq_id).all()

        if not user_answers:
            return {
                "mcq_id": mcq_id,
                "question": mcq.question,
                "total_attempts": 0,
                "correct_attempts": 0,
                "success_rate": 0.0,
                "average_time_seconds": None,
                "most_selected_wrong_answer": None
            }

        total_attempts = len(user_answers)
        correct_attempts = len([ans for ans in user_answers if ans.is_correct])
        success_rate = (correct_attempts / total_attempts) * 100

        # Calculate average time
        times = [ans.time_taken_seconds for ans in user_answers if ans.time_taken_seconds]
        average_time = sum(times) / len(times) if times else None

        # Find most selected wrong answer
        wrong_answers = [ans for ans in user_answers if not ans.is_correct]
        if wrong_answers:
            from collections import Counter
            wrong_selections = []
            for ans in wrong_answers:
                selected = safe_json_loads(ans.selected_answers, [])
                wrong_selections.extend(selected)

            most_common = Counter(wrong_selections).most_common(1)
            most_selected_wrong = most_common[0][0] if most_common else None
        else:
            most_selected_wrong = None

        return {
            "mcq_id": mcq_id,
            "question": mcq.question,
            "total_attempts": total_attempts,
            "correct_attempts": correct_attempts,
            "success_rate": round(success_rate, 2),
            "average_time_seconds": round(average_time, 2) if average_time else None,
            "most_selected_wrong_answer": most_selected_wrong
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCQ statistics {mcq_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get MCQ statistics")


@router.post("/lessons/{lesson_id}/mcqs/bulk", status_code=status.HTTP_201_CREATED)
async def create_bulk_mcqs(
        lesson_id: int,
        mcqs: List[MCQCreate],
        db: Session = Depends(get_db)
):
    """Create multiple MCQs for a lesson at once"""
    try:
        # Verify lesson exists
        lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")

        created_mcqs = []

        for i, mcq_data in enumerate(mcqs):
            # Ensure all MCQs are for the same lesson
            mcq_data.lesson_id = lesson_id
            mcq_data.order_index = i

            # Validate each MCQ
            if not mcq_data.correct_answers or max(mcq_data.correct_answers) >= len(mcq_data.options):
                raise HTTPException(status_code=400, detail=f"Invalid correct answer indices for MCQ {i + 1}")

            # Prepare data
            mcq_dict = mcq_data.model_dump()
            mcq_dict["options"] = safe_json_dumps([opt.model_dump() for opt in mcq_data.options])
            mcq_dict["correct_answers"] = safe_json_dumps(mcq_data.correct_answers)
            mcq_dict["hints"] = safe_json_dumps(mcq_data.hints or [])
            mcq_dict["tags"] = safe_json_dumps(mcq_data.tags or [])

            # Handle enums
            if hasattr(mcq_dict["question_type"], 'value'):
                mcq_dict["question_type"] = mcq_dict["question_type"].value
            if hasattr(mcq_dict["difficulty"], 'value'):
                mcq_dict["difficulty"] = mcq_dict["difficulty"].value

            db_mcq = MCQ(**mcq_dict)
            db.add(db_mcq)
            created_mcqs.append(db_mcq)

        db.commit()

        # Refresh all created MCQs
        for mcq in created_mcqs:
            db.refresh(mcq)

        logger.info(f"Created {len(created_mcqs)} MCQs for lesson {lesson_id}")

        return {
            "message": f"Successfully created {len(created_mcqs)} MCQs",
            "lesson_id": lesson_id,
            "mcq_ids": [mcq.id for mcq in created_mcqs]
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create bulk MCQs for lesson {lesson_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create MCQs")
# Health check
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "course_service"}