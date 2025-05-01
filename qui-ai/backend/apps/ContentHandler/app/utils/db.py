# app/db.py
import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
import redis
from fastapi import HTTPException

load_dotenv()

Base = declarative_base()
engine = None

if os.getenv("ENVIRONMENT") == "production":
    # Azure PostgreSQL with token refresh
    credential = DefaultAzureCredential()
    token = credential.get_token("https://ossrdbms-aad.database.windows.net/.default").token
    encoded_token = quote_plus(token)

    DATABASE_URL = (
        f"postgresql+psycopg2://{os.getenv('PGUSER')}:{encoded_token}@"
        f"{os.getenv('PGHOST')}:{os.getenv('PGPORT')}/{os.getenv('PGDATABASE')}?sslmode=require"
    )

    engine = create_engine(DATABASE_URL)


    @event.listens_for(engine, "engine_connect")
    def refresh_token(dbapi_connection, connection_record):
        new_token = DefaultAzureCredential().get_token("https://ossrdbms-aad.database.windows.net/.default").token
        dbapi_connection.password = quote_plus(new_token)
else:
    # Local PostgreSQL
    DATABASE_URL = (
        f"postgresql+psycopg2://{os.getenv('PGUSER')}:{os.getenv('PGPASSWORD')}@"
        f"host.docker.internal:5432/{os.getenv('PGDATABASE')}"
    )
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis_client():
    try:
        return redis.Redis(
            host=os.getenv("REDIS_HOST"),
            port=int(os.getenv("REDIS_PORT")),
            password=os.getenv("REDIS_PASSWORD"),
            ssl=os.getenv("ENVIRONMENT") == "production",
            decode_responses=True
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Redis connection failed: {str(e)}"
        )