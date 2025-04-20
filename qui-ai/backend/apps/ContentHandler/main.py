# main.py
from fastapi import FastAPI
from app.routes import router as app_router  # Assuming we'll set up routes in 'app/routes.py'

app = FastAPI()

app.include_router(app_router)
