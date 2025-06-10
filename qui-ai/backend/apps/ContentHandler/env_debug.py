#!/usr/bin/env python3
"""
Environment Debug Script
Run this to diagnose environment variable loading issues
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def check_env_files():
    """Check for .env files in various locations"""
    print("=== Checking for .env files ===")

    possible_locations = [
        Path.cwd() / ".env",
        Path.cwd() / "config" / ".env",
        project_root / ".env",
        project_root / "config" / ".env",
        project_root.parent / ".env",
    ]

    found_files = []

    for location in possible_locations:
        exists = location.exists()
        print(f"  {location}: {'✓ EXISTS' if exists else '✗ NOT FOUND'}")

        if exists and location.is_file():
            found_files.append(location)
            try:
                with open(location, 'r') as f:
                    lines = f.readlines()
                    print(f"    File size: {location.stat().st_size} bytes")
                    print(f"    Lines: {len(lines)}")

                    # Show first few non-comment, non-empty lines
                    content_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
                    print(f"    Content lines: {len(content_lines)}")

                    if content_lines:
                        print("    First few variables:")
                        for i, line in enumerate(content_lines[:5]):
                            if '=' in line:
                                key, value = line.split('=', 1)
                                print(f"      {key.strip()}={value.strip()[:20]}...")

            except Exception as e:
                print(f"    ✗ Error reading file: {e}")

    return found_files


def test_manual_env_loading():
    """Test manual environment loading"""
    print("\n=== Testing Manual Environment Loading ===")

    from dotenv import load_dotenv

    # Try to load .env from current directory
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        print(f"Loading from: {env_path}")
        load_dotenv(env_path, override=True)

        # Check if variables are loaded
        test_vars = ['SUPABASE_URL', 'SUPABASE_ANON_KEY', 'REDIS_URL']
        for var in test_vars:
            value = os.getenv(var)
            if value:
                print(f"  ✓ {var}: {value[:30]}...")
            else:
                print(f"  ✗ {var}: NOT LOADED")
    else:
        print(f"No .env file found at: {env_path}")


def check_system_env():
    """Check system environment variables"""
    print("\n=== Checking System Environment Variables ===")

    relevant_vars = []
    for key, value in os.environ.items():
        if any(term in key.upper() for term in ['SUPABASE', 'REDIS', 'DATABASE', 'API_KEY']):
            relevant_vars.append((key, value))

    if relevant_vars:
        print("Found relevant environment variables:")
        for key, value in relevant_vars:
            masked_value = value[:20] + "..." if len(value) > 20 else value
            print(f"  {key}: {masked_value}")
    else:
        print("No relevant environment variables found in system environment")


def test_config_loading():
    """Test the actual config loading"""
    print("\n=== Testing Config Loading ===")

    try:
        # Import and test the config
        from app.config.settings import get_settings, debug_environment

        print("Calling debug_environment()...")
        debug_environment()

        print("\nTesting config properties...")
        config = get_settings()

        print(f"SUPABASE_URL: {config.SUPABASE_URL[:30] + '...' if config.SUPABASE_URL else 'NOT SET'}")
        print(f"SUPABASE_ANON_KEY: {config.SUPABASE_ANON_KEY[:30] + '...' if config.SUPABASE_ANON_KEY else 'NOT SET'}")
        print(f"REDIS_URL: {config.REDIS_URL[:30] + '...' if config.REDIS_URL else 'NOT SET'}")

        # Test validation
        is_valid, errors = config.is_valid()
        print(f"\nConfiguration valid: {is_valid}")
        if errors:
            print("Errors:")
            for error in errors:
                print(f"  - {error}")

    except Exception as e:
        print(f"Error loading config: {e}")
        import traceback
        traceback.print_exc()


def create_sample_env():
    """Create a sample .env file if none exists"""
    print("\n=== Creating Sample .env File ===")

    env_path = Path.cwd() / ".env"

    if env_path.exists():
        print(f"✓ .env file already exists at: {env_path}")
        return

    sample_content = """
# Sample .env file - Update with your actual values
SUPABASE_URL=https://ewvvzrxmjprjernhceun.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV3dnZ6cnhtanByamVybmhjZXVuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDc3OTMxOTEsImV4cCI6MjA2MzM2OTE5MX0._y1B4vSjLSPKez_7lnR1D1VGGpi1hkySV5xIzn7DbBg
REDIS_URL=redis://default:q7vaO90Ie5M2poP1OE8czfEgvUMKaRlr@redis-16617.c245.us-east-1-3.ec2.redns.redis-cloud.com:16617
ENVIRONMENT=development
DEBUG=true
""".strip()

    try:
        with open(env_path, 'w') as f:
            f.write(sample_content)
        print(f"✓ Created sample .env file at: {env_path}")
        print("Please update the values with your actual credentials")
    except Exception as e:
        print(f"✗ Error creating .env file: {e}")


def main():
    """Main debug function"""
    print("Environment Loading Debug Script")
    print("=" * 50)
    print(f"Python version: {sys.version}")
    print(f"Current working directory: {Path.cwd()}")
    print(f"Script location: {Path(__file__).parent}")

    # Check for .env files
    found_files = check_env_files()

    # If no .env files found, offer to create one
    if not found_files:
        print("\n⚠️  No .env files found!")
        create_sample_env()

    # Test manual loading
    test_manual_env_loading()

    # Check system environment
    check_system_env()

    # Test config loading
    test_config_loading()

    print("\n" + "=" * 50)
    print("Debug complete!")

    # Recommendations
    print("\n=== Recommendations ===")
    if not found_files:
        print("1. Create a .env file in your project root")
        print("2. Copy the values from paste.txt to your .env file")
    else:
        print("1. Verify your .env file contains the correct values")
        print("2. Check that the file is in the correct location")
        print("3. Ensure the file is readable")

    print("4. Restart your application after fixing the .env file")


if __name__ == "__main__":
    main()