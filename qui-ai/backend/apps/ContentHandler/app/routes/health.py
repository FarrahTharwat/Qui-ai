from fastapi import APIRouter
from sqlalchemy.sql import text  # <-- Add this import
from app.utils.db import SessionLocal

router = APIRouter(tags=["Health"])

@router.get('/db-health')
def check_db():
    db = None
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))  # <-- Wrap SQL in text()
        return {"status": "Database connected"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if db:
            db.close()