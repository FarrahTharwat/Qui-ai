# main.py
"""FastAPI main application with document processing and MCQ generation endpoints"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Import routers
from app.routes.upload import router as upload_router
from app.routes.mcq import router as mcq_router

# Import MCQ service for model loading
from app.services.mcq_service import mcq_service
from app.core.mcq_generator import load_models

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

    # Load MCQ models at startup
    try:
        logger.info("Loading MCQ generation models...")
        load_models()
        logger.info("MCQ models loaded successfully!")
    except Exception as e:
        logger.error(f"Failed to load MCQ models: {e}")
        logger.warning("MCQ generation will not be available")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down FastAPI application...")


# Create FastAPI app
app = FastAPI(
    title="Document Processing & MCQ Generation API",
    description="API for PDF document processing with cleaning, summarization, storage, and MCQ generation using T5 + RoBERTa",
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
app.include_router(mcq_router)


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
        "message": "Document Processing & MCQ Generation API",
        "version": "1.0.0",
        "description": "Advanced API for document processing and MCQ generation using T5 + RoBERTa models",
        "endpoints": {
            "document_processing": {
                "upload": "/api/v1/upload",
                "status": "/api/v1/status/{session_id}",
                "document": "/api/v1/document/{session_id}",
                "documents": "/api/v1/documents",
                "health": "/api/v1/health"
            },
            "mcq_generation": {
                "generate": "/api/v1/mcq/generate/{document_id}",
                "status": "/api/v1/mcq/status/{session_id}",
                "list": "/api/v1/mcq/document/{document_id}",
                "get": "/api/v1/mcq/{mcq_id}",
                "update": "/api/v1/mcq/{mcq_id}",
                "delete": "/api/v1/mcq/{mcq_id}",
                "bulk_delete": "/api/v1/mcq/document/{document_id}"
            }
        },
        "features": [
            "PDF document processing and cleaning",
            "Text summarization",
            "Supabase storage integration",
            "T5-based question generation",
            "RoBERTa-based answer extraction",
            "Quality MCQ generation with distractors",
            "Difficulty assessment",
            "Confidence scoring"
        ]
    }


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check if MCQ models are loaded
        from app.core.mcq_generator import _models_loaded
        
        return {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",  # Will be replaced with actual timestamp
            "services": {
                "api": "running",
                "mcq_models": "loaded" if _models_loaded else "not_loaded",
                "database": "connected"  # Could add actual DB health check
            },
            "version": "1.0.0"
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "services": {
                    "api": "running",
                    "mcq_models": "error",
                    "database": "unknown"
                }
            }
        )


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