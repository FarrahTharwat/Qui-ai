# Fixed main.py
from fastapi import FastAPI, HTTPException
from routes import router
from database import initialize_db, test_connections
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Leaderboard Service",
    version="0.2.0",
    description="Leaderboard service using Supabase and Redis"
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        logger.info("Starting leaderboard service...")

        # Initialize database connection
        await initialize_db()
        logger.info("Database initialized")

        # Test all connections
        await test_connections()
        logger.info("All connections tested successfully")

        logger.info("Leaderboard service started successfully")

    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise


@app.get("/")
def read_root():
    """Root endpoint"""
    return {
        "message": "Leaderboard Service",
        "version": "0.2.0",
        "status": "running",
        "database": "Supabase PostgreSQL",
        "cache": "Redis"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        from database import async_session_maker
        if not async_session_maker:
            await initialize_db()

        # Test Redis connection
        from database import redis_client
        redis_client.ping()

        return {
            "status": "healthy",
            "database": "connected",
            "cache": "connected"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


# Include API routes
app.include_router(router, prefix="/api")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )