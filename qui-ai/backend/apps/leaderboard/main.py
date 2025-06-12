# Updated main.py with CORS and proper port configuration
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from routes import router
from database import initialize_db, test_connections
import asyncio
import logging
import os
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    try:
        logger.info("Starting leaderboard service...")

        # Initialize database connection
        await initialize_db()
        logger.info("Database initialized")

        # Test all connections
        await test_connections()
        logger.info("All connections tested successfully")

        logger.info("Leaderboard service started successfully")

        yield

    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise
    finally:
        logger.info("Shutting down leaderboard service...")


app = FastAPI(
    title="Leaderboard Service",
    version="0.2.0",
    description="Leaderboard service using Supabase and Redis",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """Root endpoint"""
    return {
        "message": "Leaderboard Service",
        "version": "0.2.0",
        "status": "running",
        "database": "Supabase PostgreSQL",
        "cache": "Redis",
        "port": 8005
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
            "cache": "connected",
            "port": 8005
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


# Include API routes
app.include_router(router, prefix="/api")

if __name__ == "__main__":
    import uvicorn

    # Get port from environment or use default 8005
    port = int(os.getenv("PORT", 8005))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )