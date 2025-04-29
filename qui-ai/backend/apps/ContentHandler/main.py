from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routes.flashcard import router as flashcards_router
import logging
import uvicorn
logging.basicConfig(level=logging.DEBUG)

app = FastAPI()

# Include routers
app.include_router(flashcards_router, prefix="/api")

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


logging.basicConfig(level=logging.INFO)

@app.on_event("startup")
async def startup():
    logging.info("Starting up...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)

@app.get("/")
async def root():
    logging.info("Root endpoint called")
    return {"status": "API Online!"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico")