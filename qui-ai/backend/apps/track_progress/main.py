from fastapi import FastAPI
from database import client  # Import the client to establish the connection
from routes import router

app = FastAPI(title="Track Progress Service")
app.include_router(router, prefix="/track", tags=["Tracking"])

