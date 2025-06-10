import json
import logging
from db_connection import SessionLocal, engine
from models import Base, Course, Topic, Lesson, DifficultyLevel, LessonType, LessonStatus

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_seed_data():
    """Create comprehensive seed data for the course service"""

    # Create all tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # Clear existing data (optional - comment out if you want to preserve existing data)
        logger.info("Clearing existing data...")
        db.query(Lesson).delete()
        db.query(Topic).delete()
        db.query(Course).delete()
        db.commit()

        # Create courses
        logger.info("Creating courses...")
        courses_data = [
            {
                "title": "Introduction to Python Programming",
                "description": "Learn Python from scratch with hands-on examples and projects. Perfect for beginners with no programming experience.",
                "difficulty": DifficultyLevel.BEGINNER,
                "estimated_duration_hours": 40,
                "is_active": True
            },
            {
                "title": "Machine Learning Fundamentals",
                "description": "Comprehensive introduction to machine learning concepts, algorithms, and practical applications using Python.",
                "difficulty": DifficultyLevel.INTERMEDIATE,
                "estimated_duration_hours": 60,
                "is_active": True
            },
            {
                "title": "Advanced Data Structures and Algorithms",
                "description": "Deep dive into complex data structures and algorithms with optimization techniques and real-world applications.",
                "difficulty": DifficultyLevel.ADVANCED,
                "estimated_duration_hours": 80,
                "is_active": True
            },
            {
                "title": "Web Development with FastAPI",
                "description": "Build modern, high-performance web APIs using FastAPI, SQLAlchemy, and PostgreSQL.",
                "difficulty": DifficultyLevel.INTERMEDIATE,
                "estimated_duration_hours": 50,
                "is_active": True
            },
            {
                "title": "Database Design and Management",
                "description": "Master database design principles, SQL optimization, and database administration best practices.",
                "difficulty": DifficultyLevel.INTERMEDIATE,
                "estimated_duration_hours": 45,
                "is_active": True
            }
        ]

        courses = []
        for course_data in courses_data:
            course = Course(**course_data)
            db.add(course)
            courses.append(course)

        db.commit()
        logger.info(f"Created {len(courses)} courses")

        # Create topics and lessons
        logger.info("Creating topics and lessons...")

        # Python Programming Course Topics
        python_topics = [
            {
                "course_id": courses[0].id,
                "title": "Python Basics",
                "description": "Introduction to Python syntax, variables, and basic operations",
                "order_index": 1,
                "difficulty": DifficultyLevel.BEGINNER,
                "prerequisites": [],
                "estimated_duration_minutes": 180,
                "lessons": [
                    {
                        "title": "What is Python?",
                        "content": "Python is a high-level, interpreted programming language known for its simple syntax and readability. Created by Guido van Rossum in 1991, Python emphasizes code readability and allows programmers to express concepts in fewer lines of code than languages like C++ or Java.",
                        "lesson_type": LessonType.THEORY,
                        "order_index": 1,
                        "learning_objectives": ["Understand what Python is", "Learn Python's history",
                                                "Identify Python's key features"],
                        "key_concepts": ["High-level language", "Interpreted language", "Code readability"],
                        "examples": ["print('Hello, World!')", "# This is a comment", "x = 5  # Variable assignment"],
                        "estimated_duration_minutes": 20,
                        "xp_reward": 10
                    },
                    {
                        "title": "Variables and Data Types",
                        "content": "Variables in Python are containers for storing data values. Python has several built-in data types including integers, floats, strings, and booleans. Unlike many other languages, Python doesn't require explicit declaration of variable types.",
                        "lesson_type": LessonType.THEORY,
                        "order_index": 2,
                        "learning_objectives": ["Understand Python variables", "Learn basic data types",
                                                "Practice variable assignment"],
                        "key_concepts": ["Variables", "Data types", "Dynamic typing"],
                        "examples": ["age = 25", "name = 'Alice'", "height = 5.8", "is_student = True"],
                        "estimated_duration_minutes": 30,
                        "xp_reward": 15
                    },
                    {
                        "title": "Basic Operations",
                        "content": "Python supports various arithmetic, comparison, and logical operations. These operations allow you to manipulate data and make decisions in your programs.",
                        "lesson_type": LessonType.PRACTICAL,
                        "order_index": 3,
                        "learning_objectives": ["Master arithmetic operations", "Understand comparison operators",
                                                "Use logical operators"],
                        "key_concepts": ["Arithmetic operators", "Comparison operators", "Logical operators"],
                        "examples": ["5 + 3", "10 > 5", "True and False", "x += 1"],
                        "estimated_duration_minutes": 25,
                        "xp_reward": 20
                    }
                ]
            },
            {
                "course_id": courses[0].id,
                "title": "Control Structures",
                "description": "Learn conditional statements, loops, and program flow control",
                "order_index": 2,
                "difficulty": DifficultyLevel.BEGINNER,
                "prerequisites": [1],
                "estimated_duration_minutes": 240,
                "lessons": [
                    {
                        "title": "If Statements",
                        "content": "Conditional statements allow your program to make decisions based on certain conditions. The if statement is the most basic form of conditional logic in Python.",
                        "lesson_type": LessonType.THEORY,
                        "order_index": 1,
                        "learning_objectives": ["Understand conditional logic", "Write if statements",
                                                "Use elif and else"],
                        "key_concepts": ["Conditional statements", "Boolean expressions", "Code blocks"],
                        "examples": ["if x > 0:", "elif x == 0:", "else:"],
                        "estimated_duration_minutes": 35,
                        "xp_reward": 20
                    },
                    {
                        "title": "For Loops",
                        "content": "For loops are used to iterate over sequences like lists, strings, or ranges. They allow you to repeat code for each item in a collection.",
                        "lesson_type": LessonType.PRACTICAL,
                        "order_index": 2,
                        "learning_objectives": ["Understand iteration", "Write for loops", "Use range() function"],
                        "key_concepts": ["Iteration", "Sequences", "Loop variables"],
                        "examples": ["for i in range(5):", "for item in list:", "for char in 'hello':"],
                        "estimated_duration_minutes": 40,
                        "xp_reward": 25
                    },
                    {
                        "title": "While Loops",
                        "content": "While loops continue executing as long as a condition remains true. They're useful when you don't know exactly how many times you need to repeat an operation.",
                        "lesson_type": LessonType.PRACTICAL,
                        "order_index": 3,
                        "learning_objectives": ["Understand while loops", "Avoid infinite loops",
                                                "Use break and continue"],
                        "key_concepts": ["While loops", "Loop conditions", "Break and continue"],
                        "examples": ["while x < 10:", "break", "continue"],
                        "estimated_duration_minutes": 35,
                        "xp_reward": 25
                    }
                ]
            },
            {
                "course_id": courses[0].id,
                "title": "Functions and Modules",
                "description": "Create reusable code with functions and organize code with modules",
                "order_index": 3,
                "difficulty": DifficultyLevel.BEGINNER,
                "prerequisites": [2],
                "estimated_duration_minutes": 200,
                "lessons": [
                    {
                        "title": "Defining Functions",
                        "content": "Functions are reusable blocks of code that perform specific tasks. They help organize code, reduce repetition, and make programs more modular and maintainable.",
                        "lesson_type": LessonType.THEORY,
                        "order_index": 1,
                        "learning_objectives": ["Define functions", "Use parameters and arguments", "Return values"],
                        "key_concepts": ["Function definition", "Parameters", "Return statements"],
                        "examples": ["def greet(name):", "return result", "greet('Alice')"],
                        "estimated_duration_minutes": 40,
                        "xp_reward": 30
                    },
                    {
                        "title": "Working with Modules",
                        "content": "Modules are files containing Python code that can be imported and used in other programs. They help organize related functions and variables together.",
                        "lesson_type": LessonType.PRACTICAL,
                        "order_index": 2,
                        "learning_objectives": ["Import modules", "Use built-in modules", "Create custom modules"],
                        "key_concepts": ["Modules", "Import statements", "Standard library"],
                        "examples": ["import math", "from datetime import date", "import my_module"],
                        "estimated_duration_minutes": 35,
                        "xp_reward": 25
                    }
                ]
            }
        ]

        # Machine Learning Course Topics
        ml_topics = [
            {
                "course_id": courses[1].id,
                "title": "Introduction to Machine Learning",
                "description": "Fundamental concepts and types of machine learning",
                "order_index": 1,
                "difficulty": DifficultyLevel.INTERMEDIATE,
                "prerequisites": [],
                "estimated_duration_minutes": 300,
                "lessons": [
                    {
                        "title": "What is Machine Learning?",
                        "content": "Machine Learning is a subset of artificial intelligence that enables computers to learn and make decisions from data without being explicitly programmed for every scenario. It involves algorithms that can identify patterns and make predictions.",
                        "lesson_type": LessonType.THEORY,
                        "order_index": 1,
                        "learning_objectives": ["Define machine learning", "Understand AI vs ML",
                                                "Identify ML applications"],
                        "key_concepts": ["Artificial Intelligence", "Pattern recognition", "Data-driven decisions"],
                        "examples": ["Email spam detection", "Recommendation systems", "Image recognition"],
                        "estimated_duration_minutes": 45,
                        "xp_reward": 20
                    },
                    {
                        "title": "Types of Machine Learning",
                        "content": "Machine learning is broadly categorized into three types: Supervised Learning (learning with labeled data), Unsupervised Learning (finding patterns in unlabeled data), and Reinforcement Learning (learning through interaction and feedback).",
                        "lesson_type": LessonType.THEORY,
                        "order_index": 2,
                        "learning_objectives": ["Distinguish ML types", "Understand supervised learning",
                                                "Understand unsupervised learning"],
                        "key_concepts": ["Supervised learning", "Unsupervised learning", "Reinforcement learning"],
                        "examples": ["Classification problems", "Clustering analysis", "Game playing AI"],
                        "estimated_duration_minutes": 50,
                        "xp_reward": 25
                    }
                ]
            },
            {
                "course_id": courses[1].id,
                "title": "Data Preprocessing",
                "description": "Cleaning and preparing data for machine learning models",
                "order_index": 2,
                "difficulty": DifficultyLevel.INTERMEDIATE,
                "prerequisites": [1],
                "estimated_duration_minutes": 280,
                "lessons": [
                    {
                        "title": "Data Cleaning Techniques",
                        "content": "Data cleaning involves identifying and correcting errors, inconsistencies, and missing values in datasets. Clean data is crucial for building accurate machine learning models.",
                        "lesson_type": LessonType.PRACTICAL,
                        "order_index": 1,
                        "learning_objectives": ["Identify data quality issues", "Handle missing values",
                                                "Remove duplicates"],
                        "key_concepts": ["Missing values", "Outliers", "Data consistency"],
                        "examples": ["df.dropna()", "df.fillna()", "df.drop_duplicates()"],
                        "estimated_duration_minutes": 60,
                        "xp_reward": 35
                    }
                ]
            }
        ]

        # Web Development Course Topics
        web_topics = [
            {
                "course_id": courses[3].id,
                "title": "FastAPI Fundamentals",
                "description": "Getting started with FastAPI framework",
                "order_index": 1,
                "difficulty": DifficultyLevel.INTERMEDIATE,
                "prerequisites": [],
                "estimated_duration_minutes": 250,
                "lessons": [
                    {
                        "title": "Introduction to FastAPI",
                        "content": "FastAPI is a modern, fast web framework for building APIs with Python 3.6+ based on standard Python type hints. It's designed to be easy to use and learn while providing high performance and automatic API documentation.",
                        "lesson_type": LessonType.THEORY,
                        "order_index": 1,
                        "learning_objectives": ["Understand FastAPI benefits", "Compare with other frameworks",
                                                "Set up development environment"],
                        "key_concepts": ["Web APIs", "Type hints", "Automatic documentation"],
                        "examples": ["from fastapi import FastAPI", "app = FastAPI()", "@app.get('/')"],
                        "estimated_duration_minutes": 40,
                        "xp_reward": 20
                    },
                    {
                        "title": "Creating Your First API",
                        "content": "Learn to create basic API endpoints using FastAPI decorators. Understand how to handle different HTTP methods and return JSON responses.",
                        "lesson_type": LessonType.PRACTICAL,
                        "order_index": 2,
                        "learning_objectives": ["Create API endpoints", "Handle HTTP methods", "Return JSON responses"],
                        "key_concepts": ["HTTP methods", "Route decorators", "JSON responses"],
                        "examples": ["@app.get('/items/{item_id}')", "return {'item_id': item_id}",
                                     "@app.post('/items/')"],
                        "estimated_duration_minutes": 50,
                        "xp_reward": 30
                    }
                ]
            }
        ]

        # Create all topics and lessons
        all_topics = python_topics + ml_topics + web_topics

        for topic_data in all_topics:
            lessons_data = topic_data.pop('lessons', [])
            topic_data['prerequisites'] = json.dumps(topic_data.get('prerequisites', []))

            topic = Topic(**topic_data)
            db.add(topic)
            db.flush()  # Get the topic ID

            for lesson_data in lessons_data:
                lesson_data['topic_id'] = topic.id
                lesson_data['prerequisites'] = json.dumps(lesson_data.get('prerequisites', []))
                lesson_data['learning_objectives'] = json.dumps(lesson_data.get('learning_objectives', []))
                lesson_data['key_concepts'] = json.dumps(lesson_data.get('key_concepts', []))
                lesson_data['examples'] = json.dumps(lesson_data.get('examples', []))
                lesson_data['status'] = LessonStatus.PUBLISHED
                lesson_data['difficulty'] = topic.difficulty

                lesson = Lesson(**lesson_data)
                db.add(lesson)

        db.commit()
        logger.info("Successfully created all topics and lessons")

        # Print summary
        course_count = db.query(Course).count()
        topic_count = db.query(Topic).count()
        lesson_count = db.query(Lesson).count()

        logger.info(f"Seed data creation completed!")
        logger.info(f"Created: {course_count} courses, {topic_count} topics, {lesson_count} lessons")

        # Print course details
        for course in db.query(Course).all():
            topics = db.query(Topic).filter(Topic.course_id == course.id).count()
            lessons = db.query(Lesson).join(Topic).filter(Topic.course_id == course.id).count()
            logger.info(f"Course: {course.title} - {topics} topics, {lessons} lessons")

    except Exception as e:
        logger.error(f"Error creating seed data: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def add_additional_courses():
    """Add more diverse courses to the database"""
    db = SessionLocal()

    try:
        additional_courses = [
            {
                "title": "DevOps and CI/CD Fundamentals",
                "description": "Learn modern DevOps practices, continuous integration, and deployment pipelines using Docker, Kubernetes, and popular CI/CD tools.",
                "difficulty": DifficultyLevel.INTERMEDIATE,
                "estimated_duration_hours": 55,
                "is_active": True
            },
            {
                "title": "Frontend Development with React",
                "description": "Build interactive user interfaces with React, including hooks, state management, and modern development practices.",
                "difficulty": DifficultyLevel.INTERMEDIATE,
                "estimated_duration_hours": 65,
                "is_active": True
            },
            {
                "title": "System Design for Scale",
                "description": "Advanced concepts in designing distributed systems, microservices architecture, and handling high-traffic applications.",
                "difficulty": DifficultyLevel.ADVANCED,
                "estimated_duration_hours": 90,
                "is_active": True
            },
            {
                "title": "Cybersecurity Essentials",
                "description": "Fundamental security concepts, threat assessment, and protection strategies for modern applications and systems.",
                "difficulty": DifficultyLevel.INTERMEDIATE,
                "estimated_duration_hours": 48,
                "is_active": True
            }
        ]

        for course_data in additional_courses:
            course = Course(**course_data)
            db.add(course)

        db.commit()
        logger.info(f"Added {len(additional_courses)} additional courses")

    except Exception as e:
        logger.error(f"Error adding additional courses: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def create_quiz_lessons():
    """Add quiz-type lessons to existing topics"""
    db = SessionLocal()

    try:
        # Get some existing topics
        topics = db.query(Topic).limit(3).all()

        quiz_lessons = [
            {
                "topic_id": topics[0].id,
                "title": "Python Basics Quiz",
                "content": "Test your understanding of Python fundamentals with this comprehensive quiz covering variables, data types, and basic operations.",
                "lesson_type": LessonType.QUIZ,
                "difficulty": DifficultyLevel.BEGINNER,
                "order_index": 99,  # Place at end of topic
                "prerequisites": json.dumps([]),
                "learning_objectives": json.dumps(
                    ["Test Python knowledge", "Identify knowledge gaps", "Reinforce learning"]),
                "key_concepts": json.dumps(["Python syntax", "Variables", "Data types"]),
                "examples": json.dumps(["Multiple choice questions", "Code completion exercises"]),
                "estimated_duration_minutes": 30,
                "xp_reward": 50,
                "status": LessonStatus.PUBLISHED,
                "metadata": json.dumps({
                    "quiz_type": "mixed",
                    "questions_count": 15,
                    "passing_score": 80
                })
            }
        ]

        for lesson_data in quiz_lessons:
            lesson = Lesson(**lesson_data)
            db.add(lesson)

        db.commit()
        logger.info(f"Added {len(quiz_lessons)} quiz lessons")

    except Exception as e:
        logger.error(f"Error adding quiz lessons: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting seed data creation...")

    # Create main seed data
    create_seed_data()

    # Add additional courses
    add_additional_courses()

    # Add quiz lessons
    create_quiz_lessons()

    logger.info("Seed data creation completed successfully!")