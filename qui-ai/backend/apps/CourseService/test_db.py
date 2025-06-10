#!/usr/bin/env python3

import sys
import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

print("🚀 Simple Database Connection Test")
print("=" * 50)

# Database configuration - Using Supabase Connection Pooler
DB_USER = "postgres.qduribatmkgppwjutcmz"  # Note the project reference in username
DB_PASSWORD = "TP4mYjwf_i@ARi2"
DB_HOST = "aws-0-eu-central-1.pooler.supabase.com"  # Pooler host
DB_PORT = "6543"  # Pooler port
DB_NAME = "postgres"

# Properly encode the password for URL
encoded_password = quote_plus(DB_PASSWORD)
DATABASE_URL = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"📊 Connection Details:")
print(f"   Host: {DB_HOST}")
print(f"   Port: {DB_PORT}")
print(f"   Database: {DB_NAME}")
print(f"   User: {DB_USER}")
print(f"   Password: {'*' * len(DB_PASSWORD)}")
print()

print("🔄 Creating engine...")
try:
    engine = create_engine(DATABASE_URL, echo=True)
    print("✅ Engine created successfully")
except Exception as e:
    print(f"❌ Failed to create engine: {e}")
    sys.exit(1)

print("🔄 Testing connection...")
try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        print(f"✅ SUCCESS: Database connection works! Query result: {row}")
except Exception as e:
    print(f"❌ FAILED: Database connection failed: {e}")
    sys.exit(1)

print("=" * 50)
print("🎉 All tests passed!")