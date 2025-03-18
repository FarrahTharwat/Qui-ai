from fastapi import FastAPI
from routes import router

app = FastAPI()

# Include routes
app.include_router(router)

@app.get("/")
async def root():
    return {"message": "Welcome to FastAPI Progress Tracker"}