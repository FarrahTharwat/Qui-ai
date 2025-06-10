from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from routes import router as course_router
from db_connection import check_db_connection

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Course Service API",
    description="API for managing courses, topics, and lessons",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(course_router)

@app.on_event("startup")
async def startup_event():
    """Check database connection on startup"""
    logger.info("Starting Course Service...")
    if check_db_connection():
        logger.info("Database connection successful")
    else:
        logger.error("Database connection failed")

@app.get("/")
async def root():
    return {"message": "Course Service API", "status": "running"}

@app.get("/health")
async def health_check():
    """Global health check"""
    db_status = "healthy" if check_db_connection() else "unhealthy"
    return {
        "service": "course_service",
        "status": "healthy",
        "database": db_status
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)