from fastapi import FastAPI
from routes import router

app = FastAPI(title="Achievements Microservice")

app.include_router(router, prefix="/achievements")


# Run with: uvicorn main:app --reload
