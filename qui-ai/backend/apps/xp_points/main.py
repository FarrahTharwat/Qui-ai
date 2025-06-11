import os
os.environ["CURL_CA_BUNDLE"] = ""
from fastapi import FastAPI
from xp_points.routes import router

app = FastAPI()
app.include_router(router)
