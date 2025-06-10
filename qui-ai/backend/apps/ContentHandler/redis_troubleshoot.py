#!/usr/bin/env python3
"""
Redis Database Troubleshooting Script
This script helps diagnose why data might not be appearing in your Redis database
"""

import redis
import json
import time
from datetime import datetime
from typing import Dict, Any, List


def connect_to_redis():
    """Try to connect to Redis using your app's configuration"""
    try:
        # Try Redis URL first (from your .env)
        import os
        from dotenv import load_dotenv

        load_dotenv()
        redis_url = os.getenv('REDIS_URL')

        if redis_url:
            print(f"🔗 Connecting via REDIS_URL...")
            r = redis.from_url(redis_url, decode_responses=True)
        else:
            print(f"🔗 Connecting via manual config...")
            r = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                password=os.getenv('REDIS_PASSWORD'),
                decode_responses=True
            )

        # Test connection
        r.ping()
        print("✅ Redis connection successful")
        return r

    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return None


def analyze_existing_data(r: redis.Redis):
    """Analyze what's currently in your Redis database"""
    print("\n" + "=" * 50)
    print("ANALYZING EXISTING DATA")
    print("=" * 50)

    try:
        # Get all keys
        all_keys = r.keys('*')
        print(f"📊 Total keys in database: {len(all_keys)}")

        if not all_keys:
            print("⚠️  Database is completely empty!")
            return

        # Categorize keys
        key_patterns = {}
        for key in all_keys:
            prefix = key.split(':')[0] if ':' in key else 'no_prefix'
            if prefix not in key_patterns:
                key_patterns[prefix] = []
            key_patterns[prefix].append(key)

        print(f"\n📋 Key patterns found:")
        for pattern, keys in key_patterns.items():
            print(f"  • {pattern}: {len(keys)} keys")
            # Show first few examples
            for key in keys[:3]:
                try:
                    key_type = r.type(key)
                    ttl = r.ttl(key)
                    ttl_info = f"TTL: {ttl}s" if ttl > 0 else "No TTL" if ttl == -1 else "Expired"
                    print(f"    - {key} [{key_type}] ({ttl_info})")
                except Exception as e:
                    print(f"    - {key} [Error reading: {e}]")

        return key_patterns

    except Exception as e:
        print(f"❌ Error analyzing data: {e}")
        return {}


def test_data_operations(r: redis.Redis):
    """Test basic data operations to ensure they work"""
    print("\n" + "=" * 50)
    print("TESTING DATA OPERATIONS")
    print("=" * 50)

    test_session_id = f"test_session_{int(time.time())}"

    try:
        # Test 1: Basic string operations
        print("🧪 Test 1: Basic string operations")
        r.set(f"test:{test_session_id}", "test_value", ex=300)  # 5 min TTL
        retrieved = r.get(f"test:{test_session_id}")
        print(f"   Set/Get test: {'✅ PASS' if retrieved == 'test_value' else '❌ FAIL'}")

        # Test 2: JSON data (like your app uses)
        print("🧪 Test 2: JSON data operations")
        test_data = {
            "status": "processing",
            "timestamp": datetime.now().isoformat(),
            "data": {"test": True}
        }
        r.set(f"status:{test_session_id}", json.dumps(test_data), ex=300)
        retrieved_json = json.loads(r.get(f"status:{test_session_id}") or "{}")
        print(f"   JSON test: {'✅ PASS' if retrieved_json.get('status') == 'processing' else '❌ FAIL'}")

        # Test 3: Check if keys appear immediately
        print("🧪 Test 3: Key visibility")
        all_keys_after = r.keys('*')
        test_keys = [k for k in all_keys_after if test_session_id in k]
        print(f"   Test keys visible: {'✅ PASS' if len(test_keys) >= 2 else '❌ FAIL'}")
        print(f"   Found test keys: {test_keys}")

        # Cleanup
        for key in test_keys:
            r.delete(key)
        print("🧹 Test cleanup completed")

    except Exception as e:
        print(f"❌ Error during testing: {e}")


def monitor_live_activity(r: redis.Redis, duration=10):
    """Monitor live Redis activity"""
    print(f"\n" + "=" * 50)
    print(f"MONITORING LIVE ACTIVITY ({duration} seconds)")
    print("=" * 50)

    try:
        initial_keys = set(r.keys('*'))
        print(f"📊 Starting with {len(initial_keys)} keys")
        print("👀 Watching for changes... (run your app now)")

        start_time = time.time()
        changes_detected = []

        while time.time() - start_time < duration:
            current_keys = set(r.keys('*'))

            # Check for new keys
            new_keys = current_keys - initial_keys
            if new_keys:
                for key in new_keys:
                    changes_detected.append(f"➕ NEW: {key}")
                    print(f"➕ NEW KEY: {key}")
                initial_keys.update(new_keys)

            # Check for deleted keys
            deleted_keys = initial_keys - current_keys
            if deleted_keys:
                for key in deleted_keys:
                    changes_detected.append(f"➖ DELETED: {key}")
                    print(f"➖ DELETED: {key}")
                initial_keys -= deleted_keys

            time.sleep(0.5)

        print(f"\n📋 Summary of changes detected:")
        if changes_detected:
            for change in changes_detected:
                print(f"   {change}")
        else:
            print("   ⚠️  No changes detected during monitoring period")

    except Exception as e:
        print(f"❌ Error during monitoring: {e}")


def check_app_specific_patterns(r: redis.Redis):
    """Check for your app's specific data patterns"""
    print("\n" + "=" * 50)
    print("CHECKING APP-SPECIFIC PATTERNS")
    print("=" * 50)

    patterns_to_check = [
        "processing:*",
        "status:*",
        "cleaned:*",
        "summary:*",
        "session:*",
        "*:session:*"
    ]

    for pattern in patterns_to_check:
        try:
            keys = r.keys(pattern)
            print(f"🔍 Pattern '{pattern}': {len(keys)} keys")

            if keys:
                # Show recent keys (first 3)
                for key in keys[:3]:
                    try:
                        key_type = r.type(key)
                        if key_type == 'string':
                            value = r.get(key)
                            if value:
                                try:
                                    parsed = json.loads(value)
                                    if isinstance(parsed, dict):
                                        print(f"   • {key}: {list(parsed.keys())}")
                                    else:
                                        print(f"   • {key}: {type(parsed).__name__}")
                                except:
                                    print(f"   • {key}: {len(value)} chars")
                            else:
                                print(f"   • {key}: [empty]")
                    except Exception as e:
                        print(f"   • {key}: [error: {e}]")
        except Exception as e:
            print(f"❌ Error checking pattern {pattern}: {e}")


def main():
    print("🔍 Redis Database Troubleshooting")
    print("=" * 50)

    # Connect to Redis
    r = connect_to_redis()
    if not r:
        print("Cannot proceed without Redis connection")
        return

    # Run diagnostics
    analyze_existing_data(r)
    test_data_operations(r)
    check_app_specific_patterns(r)

    # Ask user if they want to monitor live activity
    print(f"\n" + "=" * 50)
    print("NEXT STEPS")
    print("=" * 50)
    print("1. If you want to monitor live Redis activity:")
    print("   - Run this script again with monitoring")
    print("   - Then trigger your app functionality")
    print("2. Check your application logs for Redis errors")
    print("3. Verify your app is using the same Redis connection")

    monitor_choice = input("\nMonitor live activity now? (y/n): ").lower().strip()
    if monitor_choice == 'y':
        monitor_live_activity(r, 15)

    print("\n✅ Troubleshooting complete!")


if __name__ == "__main__":
    main()