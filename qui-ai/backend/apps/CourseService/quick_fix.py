# Script to populate your database with test lessons for navigation testing

from sqlalchemy.orm import Session
from db_connection import get_db
from models import Course, Topic, Lesson, LessonStatus


def add_more_lessons():
    """Add more lessons to topic 1 for testing navigation"""
    db = next(get_db())

    try:
        # Check if we already have lesson 1
        lesson_1 = db.query(Lesson).filter(Lesson.id == 1).first()
        if not lesson_1:
            print("Lesson 1 not found. Please make sure your database has the initial lesson.")
            return

        topic_id = lesson_1.topic_id
        print(f"Adding lessons to topic {topic_id}")

        # Check how many lessons already exist in this topic
        existing_lessons = db.query(Lesson).filter(Lesson.topic_id == topic_id).order_by(Lesson.order_index).all()
        print(f"Found {len(existing_lessons)} existing lessons:")
        for lesson in existing_lessons:
            print(f"  - Lesson {lesson.id}: {lesson.title} (order: {lesson.order_index})")

        # Add more lessons if we have fewer than 3
        if len(existing_lessons) < 3:
            next_order = max([l.order_index for l in existing_lessons]) + 1 if existing_lessons else 1

            lessons_to_add = [
                {
                    "title": "Control Structures (If/Else)",
                    "content": "Learn about conditional statements and control flow in Python.",
                    "order_index": next_order
                },
                {
                    "title": "Loops and Iteration",
                    "content": "Master for loops, while loops, and iteration techniques.",
                    "order_index": next_order + 1
                }
            ]

            for lesson_data in lessons_to_add:
                if next_order <= 3:  # Only add if we don't already have this order
                    lesson = Lesson(
                        title=lesson_data["title"],
                        content=lesson_data["content"],
                        topic_id=topic_id,
                        lesson_type="THEORY",
                        difficulty="BEGINNER",
                        order_index=lesson_data["order_index"],
                        prerequisites="[]",
                        learning_objectives="[]",
                        key_concepts="[]",
                        examples="[]",
                        estimated_duration_minutes=25,
                        xp_reward=15,
                        status=LessonStatus.PUBLISHED.value,
                        lesson_metadata="{}"
                    )
                    db.add(lesson)
                    next_order += 1

            db.commit()
            print(f"Added {len(lessons_to_add)} new lessons")
        else:
            print("Topic already has enough lessons for testing")

        # Show final state
        all_lessons = db.query(Lesson).filter(Lesson.topic_id == topic_id).order_by(Lesson.order_index).all()
        print(f"\nFinal lesson structure for topic {topic_id}:")
        for lesson in all_lessons:
            print(f"  - Lesson {lesson.id}: {lesson.title} (order: {lesson.order_index}, status: {lesson.status})")

    except Exception as e:
        db.rollback()
        print(f"Error adding lessons: {e}")
    finally:
        db.close()


def add_second_topic_with_lessons():
    """Add a second topic with lessons to test cross-topic navigation"""
    db = next(get_db())

    try:
        # Get the course ID from lesson 1
        lesson_1 = db.query(Lesson).filter(Lesson.id == 1).first()
        if not lesson_1:
            print("Lesson 1 not found")
            return

        topic_1 = db.query(Topic).filter(Topic.id == lesson_1.topic_id).first()
        course_id = topic_1.course_id

        # Check if we already have a second topic
        existing_topics = db.query(Topic).filter(Topic.course_id == course_id).order_by(Topic.order_index).all()
        print(f"Found {len(existing_topics)} existing topics in course {course_id}")

        if len(existing_topics) < 2:
            # Create second topic
            next_topic_order = max([t.order_index for t in existing_topics]) + 1

            topic_2 = Topic(
                title="Functions and Modules",
                description="Learn about functions, parameters, and Python modules",
                course_id=course_id,
                order_index=next_topic_order,
                difficulty="BEGINNER",
                prerequisites="[]",
                estimated_duration_minutes=90
            )
            db.add(topic_2)
            db.commit()
            db.refresh(topic_2)

            print(f"Created topic: {topic_2.title} (ID: {topic_2.id})")

            # Add lessons to the new topic
            lessons_data = [
                {
                    "title": "Defining Functions",
                    "content": "Learn how to define and call functions in Python.",
                    "order_index": 1
                },
                {
                    "title": "Function Parameters and Arguments",
                    "content": "Master different types of parameters and argument passing.",
                    "order_index": 2
                }
            ]

            for lesson_data in lessons_data:
                lesson = Lesson(
                    title=lesson_data["title"],
                    content=lesson_data["content"],
                    topic_id=topic_2.id,
                    lesson_type="THEORY",
                    difficulty="BEGINNER",
                    order_index=lesson_data["order_index"],
                    prerequisites="[]",
                    learning_objectives="[]",
                    key_concepts="[]",
                    examples="[]",
                    estimated_duration_minutes=30,
                    xp_reward=20,
                    status=LessonStatus.PUBLISHED.value,
                    lesson_metadata="{}"
                )
                db.add(lesson)

            db.commit()
            print(f"Added {len(lessons_data)} lessons to the new topic")
        else:
            print("Course already has multiple topics")

    except Exception as e:
        db.rollback()
        print(f"Error adding second topic: {e}")
    finally:
        db.close()


def show_navigation_structure():
    """Show the complete navigation structure"""
    db = next(get_db())

    try:
        print("\n=== COMPLETE NAVIGATION STRUCTURE ===")

        courses = db.query(Course).all()
        for course in courses:
            print(f"\nCourse {course.id}: {course.title}")

            topics = db.query(Topic).filter(Topic.course_id == course.id).order_by(Topic.order_index).all()
            for topic in topics:
                print(f"  Topic {topic.id}: {topic.title} (order: {topic.order_index})")

                lessons = db.query(Lesson).filter(Lesson.topic_id == topic.id).order_by(Lesson.order_index).all()
                for lesson in lessons:
                    print(
                        f"    Lesson {lesson.id}: {lesson.title} (order: {lesson.order_index}, status: {lesson.status})")

    except Exception as e:
        print(f"Error showing structure: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    print("1. Adding more lessons to existing topic...")
    add_more_lessons()

    print("\n2. Adding second topic with lessons...")
    add_second_topic_with_lessons()

    print("\n3. Showing complete structure...")
    show_navigation_structure()