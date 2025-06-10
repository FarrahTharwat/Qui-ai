#!/usr/bin/env python3

import sys
import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

print("🔧 Supabase Connection String Helper")
print("=" * 60)

# Your Supabase project reference
PROJECT_REF = "qduribatmkgppwjutcmz"

print("📋 Based on your project reference, here are the possible connection strings:")
print(f"   Project Reference: {PROJECT_REF}")
print()

# Ask user for their actual password
print("🔐 Please enter your database password:")
print("   (This should be the password you set when creating your Supabase project)")
print("   (NOT the anon key or service role key)")
password = input("Password: ").strip()

if not password:
    print("❌ Password cannot be empty!")
    sys.exit(1)

# Encode password for URL
encoded_password = quote_plus(password)

# Generate different connection string options
connection_options = [
    {
        "name": "Direct Connection",
        "url": f"postgresql://postgres:{encoded_password}@db.{PROJECT_REF}.supabase.co:5432/postgres",
        "display": f"postgresql://postgres:***@db.{PROJECT_REF}.supabase.co:5432/postgres"
    },
    {
        "name": "Connection Pooler (Transaction Mode)",
        "url": f"postgresql://postgres.{PROJECT_REF}:{encoded_password}@aws-0-us-west-1.pooler.supabase.com:6543/postgres",
        "display": f"postgresql://postgres.{PROJECT_REF}:***@aws-0-us-west-1.pooler.supabase.com:6543/postgres"
    },
    {
        "name": "Connection Pooler (Session Mode)",
        "url": f"postgresql://postgres.{PROJECT_REF}:{encoded_password}@aws-0-us-west-1.pooler.supabase.com:5432/postgres",
        "display": f"postgresql://postgres.{PROJECT_REF}:***@aws-0-us-west-1.pooler.supabase.com:5432/postgres"
    }
]

print("\n🔄 Testing connection options...")

successful_config = None

for i, config in enumerate(connection_options, 1):
    print(f"\n{i}. Testing {config['name']}...")
    print(f"   URL: {config['display']}")

    try:
        engine = create_engine(config['url'], connect_args={"connect_timeout": 10})

        with engine.connect() as connection:
            result = connection.execute(text("SELECT current_database(), version()"))
            row = result.fetchone()
            print(f"   ✅ SUCCESS!")
            print(f"   Database: {row[0]}")
            print(f"   PostgreSQL Version: {row[1][:50]}...")
            successful_config = config
            break

    except Exception as e:
        print(f"   ❌ FAILED: {str(e)[:100]}...")

print("\n" + "=" * 60)

if successful_config:
    print("🎉 SUCCESS! Working connection found!")
    print(f"✅ Working configuration: {successful_config['name']}")
    print(f"\n📝 Add this to your .env file:")
    print(f"DATABASE_URL={successful_config['url']}")