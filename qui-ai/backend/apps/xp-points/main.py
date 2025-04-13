from fastapi import FastAPI
from routes import router

app = FastAPI()

# Include routes
app.include_router(router)

# Run with: uvicorn main:app --reload
