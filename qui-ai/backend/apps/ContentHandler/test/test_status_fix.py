# test_status_fix.py
"""Test script to verify the status endpoint fix"""

import asyncio
import logging
from datetime import datetime

# Your imports
from app.services.database_operations import get_document_service
from app.config.database import get_redis_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_status_fix():
    """Test the fixed status functionality"""
    print(f"🧪 Testing Status Fix - {datetime.now()}")
    print("=" * 60)

    # Get a real session ID from your Redis data
    test_session_ids = [
        "1a4b73c7-ead0-4822-97f9-d39b8c3724ab",
        "5abea146-4868-4d49-9201-c481c4c80c85",
        "3f114ddd-b126-421a-b8c2-deb9e28615bb"
    ]

    document_service = get_document_service()

    for session_id in test_session_ids:
        print(f"\n📋 Testing session: {session_id}")
        print("-" * 40)

        try:
            # Test with timeout like your endpoint does
            status_info = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    document_service.get_session_status,
                    session_id
                ),
                timeout=5.0
            )

            print(f"✅ Status retrieved successfully!")
            print(f"   Current Status: {status_info.get('current_status')}")
            print(f"   Database Saved: {status_info.get('database_saved')}")
            print(f"   Document ID: {status_info.get('document_id')}")
            print(f"   Last Update: {status_info.get('last_update')}")

            if status_info.get('error'):
                print(f"⚠️  Error in response: {status_info.get('error')}")

        except asyncio.TimeoutError:
            print("❌ TIMEOUT: Still hanging!")
            print("   The fix didn't work - check database operations")

        except Exception as e:
            print(f"❌ ERROR: {str(e)}")

    print(f"\n🏁 Test completed - {datetime.now()}")


async def test_redis_only():
    """Test Redis operations directly"""
    print(f"\n🔍 Testing Redis Only - {datetime.now()}")
    print("=" * 60)

    redis_manager = get_redis_manager()

    test_session_ids = [
        "1a4b73c7-ead0-4822-97f9-d39b8c3724ab",
        "5abea146-4868-4d49-9201-c481c4c80c85"
    ]

    for session_id in test_session_ids:
        print(f"\n📋 Redis test for session: {session_id}")
        try:
            status = redis_manager.get_session_status(session_id)
            print(f"✅ Redis Status: {status}")
        except Exception as e:
            print(f"❌ Redis Error: {str(e)}")


if __name__ == "__main__":
    print("🚀 Starting Status Fix Tests")

    # Test Redis first (should be fast)
    asyncio.run(test_redis_only())

    # Test full status method (this was hanging before)
    asyncio.run(test_status_fix())