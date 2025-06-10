# main.py
"""FastAPI main application with document processing endpoints"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Import the upload router
from app.routes.upload import router as upload_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    logger.info("Starting FastAPI application...")

    # Create necessary directories
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("processed", exist_ok=True)
    os.makedirs("static/images", exist_ok=True)

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down FastAPI application...")


# Create FastAPI app
app = FastAPI(
    title="Document Processing API",
    description="API for PDF document processing with cleaning, summarization, and storage",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure appropriately for production
)

# Include routers
app.include_router(upload_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Document Processing API",
        "version": "1.0.0",
        "endpoints": {
            "upload": "/api/v1/upload",
            "status": "/api/v1/status/{session_id}",
            "document": "/api/v1/document/{session_id}",
            "documents": "/api/v1/documents",
            "health": "/api/v1/health"
        }
    }


if __name__ == "__main__":
    # Configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    workers = int(os.getenv("WORKERS", "1"))

    # Run the application
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=os.getenv("DEBUG", "false").lower() == "true",
        log_level="info"
    )