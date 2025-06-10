from sqlalchemy import text
from db_connection import engine, Base
from models import Course, Topic, Lesson


def drop_views_and_recreate_tables():
    """
    Drop dependent views first, then recreate all tables and views
    """
    with engine.connect() as conn:
        try:
            # Start a transaction
            trans = conn.begin()

            print("Dropping dependent views...")
            # Drop the views that depend on the tables
            conn.execute(text("DROP VIEW IF EXISTS active_courses CASCADE;"))
            conn.execute(text("DROP VIEW IF EXISTS published_lessons_with_metadata CASCADE;"))

            print("Dropping functions...")
            # Drop any functions that might depend on the tables
            conn.execute(text("DROP FUNCTION IF EXISTS get_course_structure(INTEGER) CASCADE;"))
            conn.execute(text("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;"))
            conn.execute(text("DROP FUNCTION IF EXISTS is_valid_json_array(TEXT) CASCADE;"))

            print("Dropping enums...")
            # Drop custom enum types
            conn.execute(text("DROP TYPE IF EXISTS difficulty_level CASCADE;"))
            conn.execute(text("DROP TYPE IF EXISTS lesson_type CASCADE;"))
            conn.execute(text("DROP TYPE IF EXISTS lesson_status CASCADE;"))

            # Commit the transaction
            trans.commit()
            print("Views, functions, and enums dropped successfully!")

        except Exception as e:
            trans.rollback()
            print(f"Error during cleanup: {e}")
            raise

    # Now drop and recreate tables using SQLAlchemy
    print("Dropping and recreating tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Recreate the views and functions
    recreate_views_and_functions()

    print("Tables recreated successfully!")


def recreate_views_and_functions():
    """
    Recreate the views and functions that were in the original schema
    """
    with engine.connect() as conn:
        try:
            trans = conn.begin()

            print("Recreating utility function...")
            # Recreate the update function
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """))

            # Recreate triggers
            conn.execute(text("""
                CREATE TRIGGER update_courses_updated_at 
                    BEFORE UPDATE ON courses 
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            """))

            conn.execute(text("""
                CREATE TRIGGER update_topics_updated_at 
                    BEFORE UPDATE ON topics 
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            """))

            conn.execute(text("""
                CREATE TRIGGER update_lessons_updated_at 
                    BEFORE UPDATE ON lessons 
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            """))

            print("Recreating views...")
            # Recreate active_courses view
            conn.execute(text("""
                CREATE VIEW active_courses AS
                SELECT 
                    c.*,
                    COUNT(DISTINCT t.id) as topic_count,
                    COUNT(DISTINCT l.id) as lesson_count,
                    SUM(CASE WHEN l.status = 'published' THEN 1 ELSE 0 END) as published_lesson_count
                FROM courses c
                LEFT JOIN topics t ON c.id = t.course_id AND t.is_active = true
                LEFT JOIN lessons l ON t.id = l.topic_id
                WHERE c.is_active = true
                GROUP BY c.id, c.title, c.description, c.difficulty, c.estimated_duration_hours, c.is_active, c.created_at, c.updated_at;
            """))

            # Recreate published_lessons_with_metadata view
            conn.execute(text("""
                CREATE VIEW published_lessons_with_metadata AS
                SELECT 
                    l.*,
                    t.title as topic_title,
                    t.course_id,
                    c.title as course_title,
                    c.difficulty as course_difficulty
                FROM lessons l
                JOIN topics t ON l.topic_id = t.id
                JOIN courses c ON t.course_id = c.id
                WHERE l.status = 'published' AND t.is_active = true AND c.is_active = true;
            """))

            # Recreate get_course_structure function
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION get_course_structure(course_id_param INTEGER)
                RETURNS TABLE (
                    course_id INTEGER,
                    course_title VARCHAR(200),
                    course_description TEXT,
                    course_difficulty VARCHAR(50),
                    topic_id INTEGER,
                    topic_title VARCHAR(200),
                    topic_order INTEGER,
                    lesson_id INTEGER,
                    lesson_title VARCHAR(200),
                    lesson_order INTEGER,
                    lesson_status VARCHAR(50)
                ) AS $$
                BEGIN
                    RETURN QUERY
                    SELECT 
                        c.id,
                        c.title,
                        c.description,
                        c.difficulty,
                        t.id,
                        t.title,
                        t.order_index,
                        l.id,
                        l.title,
                        l.order_index,
                        l.status
                    FROM courses c
                    LEFT JOIN topics t ON c.id = t.course_id AND t.is_active = true
                    LEFT JOIN lessons l ON t.id = l.topic_id
                    WHERE c.id = course_id_param AND c.is_active = true
                    ORDER BY t.order_index, l.order_index;
                END;
                $$ LANGUAGE plpgsql;
            """))

            trans.commit()
            print("Views and functions recreated successfully!")

        except Exception as e:
            trans.rollback()
            print(f"Error recreating views and functions: {e}")
            # Don't raise here as the main tables are already created


if __name__ == "__main__":
    drop_views_and_recreate_tables()