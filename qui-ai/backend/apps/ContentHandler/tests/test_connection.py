# test_connection.py
import os
import sys
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

# Import engine
from .app.db import engine  # Ensure `app` directory has __init__.py

try:
    with engine.connect() as conn:
        print("✅ Connected to PostgreSQL!")  # Fixed indentation and message
except Exception as e:
    print(f"❌ Connection failed: {e}")  # Added f-string for error