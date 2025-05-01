from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routes.flashcard import router as flashcards_router
from app.utils.db import get_redis_client, SessionLocal
from app.config import get_settings
import logging
from app.routes.health import router as health_router
from app.routes.upload import router as upload_router
from app.routes.cleaner import router as cleaner_router


settings = get_settings()

# Logging setup
logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)

app = FastAPI()
app.include_router(health_router)
app.include_router(upload_router, prefix="/api")
app.include_router(cleaner_router, prefix="/api")

# Redis client setup
redis_client = get_redis_client()

# Routers
app.include_router(flashcards_router, prefix="/api")

# Static files (for things like favicon)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "redis_status": "connected" if redis_client.ping() else "disconnected"
    }


@app.get("/")
async def root():
    logging.info("Root endpoint called")
    return {"status": "API Online!"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")


@app.on_event("startup")
async def startup_event():
    logging.info("🚀 FastAPI app is starting...")



@app.on_event("shutdown")
async def shutdown_event():
    logging.info("🛑 FastAPI app is shutting down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000 if settings.environment == "development" else 80,
        reload=settings.environment == "development"
    )
