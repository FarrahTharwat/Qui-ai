import os
os.environ["CURL_CA_BUNDLE"] = ""
from fastapi import FastAPI
from achievements.routes import router

app = FastAPI()
app.include_router(router)
