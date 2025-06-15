#!/usr/bin/env python3
"""
Improved test script to verify the database function works correctly
This version has better import handling and more detailed debugging
"""

import json
import sys
import os
from pathlib import Path

# Add multiple possible paths to find your modules
possible_paths = [
    str(Path.cwd()),
    str(Path.cwd() / "app"),
    str(Path(__file__).parent),
    str(Path(__file__).parent / "app"),
    str(Path(__file__).parent.parent),
    str(Path(__file__).parent.parent / "app"),
]

for path in possible_paths:
    if path not in sys.path:
        sys.path.insert(0, path)

print("Python path:", sys.path[:3])  # Show first 3 paths
print("Current working directory:", Path.cwd())
print("Script location:", Path(__file__).parent if __file__ else "Unknown")

# Try different import strategies
DatabaseConfig = None
import_error = None

# Strategy 1: Direct import from config
try:
    from config.database import DatabaseConfig

    print("✓ Successfully imported DatabaseConfig from config.database")
except ImportError as e:
    print(f"✗ Failed to import from config.database: {e}")
    import_error = e

# Strategy 2: Import from app.config
if DatabaseConfig is None:
    try:
        from app.config.database import DatabaseConfig

        print("✓ Successfully imported DatabaseConfig from app.config.database")
    except ImportError as e:
        print(f"✗ Failed to import from app.config.database: {e}")
        import_error = e

# Strategy 3: Try direct file import
if DatabaseConfig is None:
    try:
        # Look for database.py file
        database_files = list(Path.cwd().rglob("database.py"))
        print(f"Found database.py files: {database_files}")

        if database_files:
            # Try to import the first one found
            db_file = database_files[0]
            spec = importlib.util.spec_from_file_location("database", db_file)
            database_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(database_module)
            DatabaseConfig = database_module.DatabaseConfig
            print(f"✓ Successfully imported DatabaseConfig from {db_file}")
    except Exception as e:
        print(f"✗ Failed direct file import: {e}")
        import_error = e

if DatabaseConfig is None:
    print(f"\n❌ Could not import DatabaseConfig. Last error: {import_error}")
    print("\nPlease check:")
    print("1. Is the script in the correct directory?")
    print("2. Are your files named correctly?")
    print("3. Try running: python -c 'from app.config.database import DatabaseConfig; print(\"Import successful\")'")
    sys.exit(1)

import importlib.util


def test_environment_loading():
    """Test if environment variables are loading correctly"""
    print("\n=== Testing Environment Loading ===")

    try:
        # Try to import settings
        try:
            from config.settings import get_settings
        except ImportError:
            from app.config.settings import get_settings

        settings = get_settings()

        # Check key variables
        supabase_url = settings.SUPABASE_URL
        supabase_key = settings.SUPABASE_ANON_KEY
        redis_url = settings.REDIS_URL

        print(f"SUPABASE_URL: {'✓ Set' if supabase_url else '✗ Missing'}")
        print(f"SUPABASE_ANON_KEY: {'✓ Set' if supabase_key else '✗ Missing'}")
        print(f"REDIS_URL: {'✓ Set' if redis_url else '✗ Missing'}")

        if supabase_url:
            print(f"Supabase URL: {supabase_url[:30]}...")

        return supabase_url and supabase_key

    except Exception as e:
        print(f"Environment test failed: {e}")
        return False


def test_database_connections():
    """Test database connections"""
    print("\n=== Testing Database Connections ===")

    try:
        db_config = DatabaseConfig()

        # Test basic initialization
        print("✓ DatabaseConfig initialized")

        # Test configuration validation
        is_valid, errors = db_config.settings.is_valid()
        if is_valid:
            print("✓ Configuration is valid")
        else:
            print(f"✗ Configuration errors: {errors}")
            return False

        # Test Supabase connection
        print("\n--- Testing Supabase Connection ---")
        if hasattr(db_config, '_supabase_manager'):
            supabase_manager = db_config._supabase_manager
        else:
            # Create managers if not exists
            from config.database import get_supabase_manager
            supabase_manager = get_supabase_manager()

        if supabase_manager.is_available():
            print("✓ Supabase connection available")

            # Test simple query
            try:
                result = supabase_manager.client.from_('documents').select('id').limit(1).execute()
                print(f"✓ Supabase query test successful: {len(result.data) if result.data else 0} records")
            except Exception as e:
                print(f"✗ Supabase query test failed: {e}")
        else:
            print("✗ Supabase connection not available")
            return False

        # Test Redis connection
        print("\n--- Testing Redis Connection ---")
        try:
            from config.database import get_redis_manager
            redis_manager = get_redis_manager()

            if redis_manager.is_available():
                print("✓ Redis connection available")

                # Test Redis operations
                test_key = "test_connection"
                test_value = "test_value"

                redis_manager.client.set(test_key, test_value, ex=30)
                retrieved_value = redis_manager.client.get(test_key)

                if retrieved_value == test_value:
                    print("✓ Redis read/write test successful")
                    redis_manager.client.delete(test_key)
                else:
                    print(f"✗ Redis read/write test failed: expected {test_value}, got {retrieved_value}")
            else:
                print("⚠ Redis connection not available (this may be okay if Redis is optional)")

        except Exception as e:
            print(f"⚠ Redis test failed: {e} (this may be okay if Redis is optional)")

        return True

    except Exception as e:
        print(f"Database connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_document_insertion():
    """Test the document insertion function"""
    print("\n=== Testing Document Insertion ===")

    try:
        db_config = DatabaseConfig()

        # Get Supabase manager
        from config.database import get_supabase_manager
        supabase_manager = get_supabase_manager()

        if not supabase_manager.is_available():
            print("✗ Supabase not available for insertion test")
            return False

        # Test data - more realistic structure
        test_data = {
            "session_id": f"test-session-{int(os.urandom(4).hex(), 16)}",
            "pdf_path": "/test/path/test_document.pdf",
            "original_cleaned_text": "This is test original text content that would come from a PDF document.",
            "combined_summary": "This is a test summary of the document content.",
            "metadata": {
                "format": "PDF",
                "title": "Test Document Title",
                "author": "Test Author",
                "page_count": 3,
                "creation_date": "2024-01-01",
                "file_size": 1024
            },
            "summarized_pages": [
                {
                    "page_number": 1,
                    "original_text": "Page 1 contains introduction and overview content.",
                    "summary": "Introduction and overview of the document topic.",
                    "key_points": ["introduction", "overview", "main topic"],
                    "relevance_score": 0.85
                },
                {
                    "page_number": 2,
                    "original_text": "Page 2 contains detailed analysis and methodology.",
                    "summary": "Detailed analysis of the methodology used.",
                    "key_points": ["analysis", "methodology", "detailed study"],
                    "relevance_score": 0.92
                }
            ],
            "summarization_metadata": {
                "model_used": "test-summarization-model",
                "total_pages": 3,
                "total_chunks": 6,
                "embedding_dimension": 384,
                "avg_relevance_score": 0.885,
                "enhancement_version": "1.0"
            }
        }

        print(f"Testing with session_id: {test_data['session_id']}")

        # Test the RPC function first
        print("\n--- Testing RPC Function ---")
        try:
            result = supabase_manager.create_document_record(test_data)

            if result and result.get('id'):
                print(f"✓ RPC insertion successful! Document ID: {result['id']}")

                # Verify the inserted document
                doc = supabase_manager.get_document_by_session(test_data['session_id'])
                if doc:
                    print(f"✓ Document verification successful: {doc['session_id']}")
                else:
                    print("⚠ Document inserted but verification failed")

                return True
            else:
                print(f"✗ RPC insertion failed: {result}")

        except Exception as e:
            print(f"✗ RPC insertion failed with error: {e}")

        # Test fallback method if RPC failed
        print("\n--- Testing Fallback Method ---")
        try:
            # Change session ID for fallback test
            test_data['session_id'] = f"test-fallback-{int(os.urandom(4).hex(), 16)}"
            print(f"Testing fallback with session_id: {test_data['session_id']}")

            result = supabase_manager.create_document_record_fallback(test_data)

            if result and result.get('id'):
                print(f"✓ Fallback insertion successful! Document ID: {result['id']}")

                # Verify the inserted document
                doc = supabase_manager.get_document_by_session(test_data['session_id'])
                if doc:
                    print(f"✓ Fallback document verification successful: {doc['session_id']}")
                else:
                    print("⚠ Fallback document inserted but verification failed")

                return True
            else:
                print(f"✗ Fallback insertion failed: {result}")

        except Exception as e:
            print(f"✗ Fallback insertion failed with error: {e}")
            import traceback
            traceback.print_exc()

        return False

    except Exception as e:
        print(f"Document insertion test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("🧪 Database Test Suite")
    print("=" * 50)

    tests_passed = 0
    total_tests = 4

    # Test 1: Environment loading
    if test_environment_loading():
        tests_passed += 1
        print("✅ Environment test PASSED")
    else:
        print("❌ Environment test FAILED")

    # Test 2: Database connections
    if test_database_connections():
        tests_passed += 1
        print("✅ Connection test PASSED")
    else:
        print("❌ Connection test FAILED")

    # Test 3: Document insertion
    if test_document_insertion():
        tests_passed += 1
        print("✅ Document insertion test PASSED")
    else:
        print("❌ Document insertion test FAILED")

    # Test 4: Overall system health
    try:
        from config.database import debug_database_connections
        debug_info = debug_database_connections()
        if debug_info and not debug_info.get('error'):
            tests_passed += 1
            print("✅ System health test PASSED")
        else:
            print("❌ System health test FAILED")
    except Exception as e:
        print(f"❌ System health test FAILED: {e}")

    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")

    if tests_passed == total_tests:
        print("🎉 All tests passed! Your database setup is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the output above for details.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)