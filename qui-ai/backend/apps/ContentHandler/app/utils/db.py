# app/db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential

# Load environment variables
load_dotenv()

# Azure AD authentication
credential = DefaultAzureCredential()
token = credential.get_token("https://ossrdbms-aad.database.windows.net/.default").token

# Environment variables
PGUSER = os.getenv("PGUSER")
PGHOST = os.getenv("PGHOST")
PGPORT = os.getenv("PGPORT")
PGDATABASE = os.getenv("PGDATABASE")

# Construct URL with token
DATABASE_URL = (
    f"postgresql+psycopg2://{PGUSER}:{token}@"
    f"{PGHOST}:{PGPORT}/{PGDATABASE}?sslmode=require"
)

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
