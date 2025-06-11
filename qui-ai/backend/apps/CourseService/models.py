from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
from enum import Enum
from db_connection import Base, engine


# Enums - Keep these as they are (they're correct)
class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class LessonType(str, Enum):
    THEORY = "theory"
    PRACTICAL = "practical"
    QUIZ = "quiz"
    PROJECT = "project"


class LessonStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# Database Models
class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    difficulty = Column(SQLEnum(DifficultyLevel, native_enum=False), default=DifficultyLevel.BEGINNER)
    estimated_duration_hours = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    topics = relationship("Topic", back_populates="course", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    order_index = Column(Integer, nullable=False)
    difficulty = Column(String, nullable=False)
    prerequisites = Column(Text)  # Stored as JSON string
    estimated_duration_minutes = Column(Integer)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = relationship("Course", back_populates="topics")
    lessons = relationship("Lesson", back_populates="topic", cascade="all, delete-orphan")

    @property
    def prerequisites_list(self):
        """Return prerequisites as a list"""
        if self.prerequisites:
            try:
                return json.loads(self.prerequisites)
            except (json.JSONDecodeError, TypeError):
                return []
        return []


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    lesson_type = Column(SQLEnum(LessonType, native_enum=False), default=LessonType.THEORY)
    difficulty = Column(SQLEnum(DifficultyLevel, native_enum=False), default=DifficultyLevel.BEGINNER)
    order_index = Column(Integer, nullable=False)
    prerequisites = Column(Text, default='[]')  # JSON array of lesson IDs
    learning_objectives = Column(Text, default='[]')  # JSON array of objectives
    key_concepts = Column(Text, default='[]')  # JSON array of key concepts
    examples = Column(Text, default='[]')  # JSON array of examples
    estimated_duration_minutes = Column(Integer, default=15)
    xp_reward = Column(Integer, default=10)
    status = Column(SQLEnum(LessonStatus, native_enum=False), default=LessonStatus.DRAFT)
    lesson_metadata = Column('metadata', Text, default='{}')  # JSON for additional data
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    topic = relationship("Topic", back_populates="lessons")
    mcqs = relationship("MCQ", back_populates="lesson", cascade="all, delete-orphan")  # ADD THIS LINE


# Create tables
Base.metadata.create_all(bind=engine)


# Pydantic Models
class CourseBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    difficulty: DifficultyLevel = DifficultyLevel.BEGINNER
    estimated_duration_hours: int = Field(default=0, ge=0)


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    difficulty: Optional[DifficultyLevel] = None
    estimated_duration_hours: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class CourseResponse(CourseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TopicBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    order_index: int = Field(..., ge=0)
    difficulty: DifficultyLevel = DifficultyLevel.BEGINNER
    prerequisites: Optional[List[int]] = []
    estimated_duration_minutes: int = Field(default=30, ge=1)


class TopicCreate(TopicBase):
    course_id: int


class TopicUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    order_index: Optional[int] = Field(None, ge=0)
    difficulty: Optional[DifficultyLevel] = None
    prerequisites: Optional[List[int]] = None
    estimated_duration_minutes: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


# FIXED TopicResponse Model
class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    order_index: int
    difficulty: str  # Keep as string since it's stored as string in DB
    prerequisites: List[int] = Field(default_factory=list)  # Changed from List[str] to List[int]
    estimated_duration_minutes: Optional[int] = None
    course_id: int
    created_at: datetime
    updated_at: datetime

    @field_validator('prerequisites', mode='before')
    @classmethod
    def parse_prerequisites(cls, v):
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                # Ensure all items are integers
                return [int(item) for item in parsed if isinstance(item, (int, str)) and str(item).isdigit()]
            except (json.JSONDecodeError, TypeError, ValueError):
                return []
        elif isinstance(v, list):
            # Ensure all items are integers
            return [int(item) for item in v if isinstance(item, (int, str)) and str(item).isdigit()]
        return []


class LessonBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    lesson_type: LessonType = LessonType.THEORY
    difficulty: DifficultyLevel = DifficultyLevel.BEGINNER
    order_index: int = Field(..., ge=0)
    prerequisites: Optional[List[int]] = []
    learning_objectives: Optional[List[str]] = []
    key_concepts: Optional[List[str]] = []
    examples: Optional[List[str]] = []
    estimated_duration_minutes: int = Field(default=15, ge=1)
    xp_reward: int = Field(default=10, ge=0)


class LessonCreate(LessonBase):
    topic_id: int


class LessonUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    lesson_type: Optional[LessonType] = None
    difficulty: Optional[DifficultyLevel] = None
    order_index: Optional[int] = Field(None, ge=0)
    prerequisites: Optional[List[int]] = None
    learning_objectives: Optional[List[str]] = None
    key_concepts: Optional[List[str]] = None
    examples: Optional[List[str]] = None
    estimated_duration_minutes: Optional[int] = Field(None, ge=1)
    xp_reward: Optional[int] = Field(None, ge=0)
    status: Optional[LessonStatus] = None
    lesson_metadata: Optional[Dict[str, Any]] = None


# FIXED LessonResponse Model with JSON field validators
class LessonResponse(LessonBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
    status: LessonStatus
    lesson_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    # Add field validators for JSON fields
    @field_validator('prerequisites', mode='before')
    @classmethod
    def parse_prerequisites(cls, v):
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return [int(item) for item in parsed if isinstance(item, (int, str)) and str(item).isdigit()]
            except (json.JSONDecodeError, TypeError, ValueError):
                return []
        elif isinstance(v, list):
            return [int(item) for item in v if isinstance(item, (int, str)) and str(item).isdigit()]
        return []

    @field_validator('learning_objectives', mode='before')
    @classmethod
    def parse_learning_objectives(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        elif isinstance(v, list):
            return v
        return []

    @field_validator('key_concepts', mode='before')
    @classmethod
    def parse_key_concepts(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        elif isinstance(v, list):
            return v
        return []

    @field_validator('examples', mode='before')
    @classmethod
    def parse_examples(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        elif isinstance(v, list):
            return v
        return []

    @field_validator('lesson_metadata', mode='before')
    @classmethod
    def parse_lesson_metadata(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        elif isinstance(v, dict):
            return v
        return {}


class LessonWithContentResponse(LessonResponse):
    """Extended lesson response for content delivery"""
    pass


class CourseStructureResponse(CourseResponse):
    topics: List[TopicResponse] = []


class TopicWithLessonsResponse(TopicResponse):
    lessons: List[LessonResponse] = []


# Add these to your existing models.py file
# Add this enum to your existing enums
class QuestionType(str, Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"


# SQLAlchemy Models - Add these to your existing models

class MCQ(Base):
    __tablename__ = "mcqs"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    question = Column(Text, nullable=False)
    question_type = Column(String(20), default=QuestionType.SINGLE_CHOICE.value)
    options = Column(Text, nullable=False)  # JSON string of options
    correct_answers = Column(Text, nullable=False)  # JSON string of correct answer indices
    explanation = Column(Text)  # Optional explanation for the answer
    difficulty = Column(String(20), default=DifficultyLevel.BEGINNER.value)
    order_index = Column(Integer, default=0)
    points = Column(Integer, default=1)  # Points awarded for correct answer
    time_limit_seconds = Column(Integer)  # Optional time limit
    hints = Column(Text)  # JSON string of hints
    tags = Column(Text)  # JSON string of tags for categorization
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lesson = relationship("Lesson", back_populates="mcqs")
    user_answers = relationship("MCQUserAnswer", back_populates="mcq", cascade="all, delete-orphan")


class MCQUserAnswer(Base):
    __tablename__ = "mcq_user_answers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # From user service
    mcq_id = Column(Integer, ForeignKey("mcqs.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    selected_answers = Column(Text, nullable=False)  # JSON string of selected answer indices
    is_correct = Column(Boolean, nullable=False)
    points_earned = Column(Integer, default=0)
    time_taken_seconds = Column(Integer)
    attempts_count = Column(Integer, default=1)
    answered_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    mcq = relationship("MCQ", back_populates="user_answers")
    lesson = relationship("Lesson")


# Update your Lesson model to include MCQ relationship
# Add this to your existing Lesson model:
# mcqs = relationship("MCQ", back_populates="lesson", cascade="all, delete-orphan")

# Pydantic Models for API

class MCQOption(BaseModel):
    text: str
    is_image: bool = False
    image_url: Optional[str] = None


class MCQCreate(BaseModel):
    lesson_id: int
    question: str
    question_type: QuestionType = QuestionType.SINGLE_CHOICE
    options: List[MCQOption]
    correct_answers: List[int]  # Indices of correct options
    explanation: Optional[str] = None
    difficulty: DifficultyLevel = DifficultyLevel.BEGINNER
    order_index: int = 0
    points: int = Field(1, ge=1, le=10)
    time_limit_seconds: Optional[int] = Field(None, ge=10, le=300)
    hints: Optional[List[str]] = []
    tags: Optional[List[str]] = []
    is_active: bool = True


class MCQUpdate(BaseModel):
    question: Optional[str] = None
    question_type: Optional[QuestionType] = None
    options: Optional[List[MCQOption]] = None
    correct_answers: Optional[List[int]] = None
    explanation: Optional[str] = None
    difficulty: Optional[DifficultyLevel] = None
    order_index: Optional[int] = None
    points: Optional[int] = Field(None, ge=1, le=10)
    time_limit_seconds: Optional[int] = Field(None, ge=10, le=300)
    hints: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class MCQResponse(BaseModel):
    id: int
    lesson_id: int
    question: str
    question_type: QuestionType
    options: List[MCQOption]
    difficulty: DifficultyLevel
    order_index: int
    points: int
    time_limit_seconds: Optional[int]
    hints: List[str]
    tags: List[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MCQWithAnswersResponse(MCQResponse):
    """MCQ response with correct answers - for admin/instructor use"""
    correct_answers: List[int]
    explanation: Optional[str]


class MCQSubmitAnswer(BaseModel):
    mcq_id: int
    selected_answers: List[int]
    time_taken_seconds: Optional[int] = None


class MCQAnswerResponse(BaseModel):
    mcq_id: int
    is_correct: bool
    correct_answers: List[int]
    explanation: Optional[str]
    points_earned: int
    time_taken_seconds: Optional[int]


class MCQUserAnswerResponse(BaseModel):
    id: int
    user_id: int
    mcq_id: int
    lesson_id: int
    selected_answers: List[int]
    is_correct: bool
    points_earned: int
    time_taken_seconds: Optional[int]
    attempts_count: int
    answered_at: datetime


class LessonMCQsResponse(BaseModel):
    lesson_id: int
    lesson_title: str
    mcqs: List[MCQResponse]
    total_mcqs: int
    total_points: int


class MCQStatistics(BaseModel):
    mcq_id: int
    question: str
    total_attempts: int
    correct_attempts: int
    success_rate: float
    average_time_seconds: Optional[float]
    most_selected_wrong_answer: Optional[int]