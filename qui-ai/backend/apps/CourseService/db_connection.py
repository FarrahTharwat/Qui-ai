from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException
import os
import logging
from urllib.parse import quote_plus

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration - Using Supabase Connection Pooler
# URL-encode the password to handle special characters
DB_USER = "postgres.qduribatmkgppwjutcmz"  # Note the project reference in username
DB_PASSWORD = "TP4mYjwf_i@ARi2"
DB_HOST = "aws-0-eu-central-1.pooler.supabase.com"  # Pooler host
DB_PORT = "6543"  # Pooler port
DB_NAME = "postgres"

# Properly encode the password for URL
encoded_password = quote_plus(DB_PASSWORD)

# Build the DATABASE_URL with properly encoded password
DATABASE_URL = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Fallback to environment variable if available
DATABASE_URL = os.getenv("DATABASE_URL", DATABASE_URL)

# Additional Supabase configuration from your .env file
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://qduribatmkgppwjutcmz.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Create engine with better configuration for Supabase
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=False  # Set to True for SQL debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Security
security = HTTPBearer(auto_error=False)


# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Enhanced authentication dependency
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Token verification - replace with actual implementation
    For now, this is a mock implementation
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization required")

    # TODO: Integrate with your actual user service
    # For development, accepting any token
    try:
        # Here you would typically:
        # 1. Validate the JWT token
        # 2. Extract user information
        # 3. Check permissions
        return {"user_id": 1, "username": "test_user", "token": credentials.credentials}
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")


# Database health check
def check_db_connection():
    """Check if database connection is working"""
    try:
        # Test with engine directly
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False


# Test the connection when module is imported
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting Database Connection Test")
    print("=" * 60)

    logger.info(f"Testing database connection...")
    logger.info(f"Database URL (password masked): postgresql://{DB_USER}:***@{DB_HOST}:{DB_PORT}/{DB_NAME}")

    print(f"📊 Connection Details:")
    print(f"   Host: {DB_HOST}")
    print(f"   Port: {DB_PORT}")
    print(f"   Database: {DB_NAME}")
    print(f"   User: {DB_USER}")
    print()

    print("🔄 Testing connection...")

    if check_db_connection():
        print("✅ SUCCESS: Database connection test passed!")
        logger.info("✅ Database connection test passed!")
    else:
        print("❌ FAILED: Database connection test failed!")
        logger.error("❌ Database connection test failed!")

    print("=" * 60)