#!/usr/bin/env python3
"""
Data Flow Debugging Script
This script helps debug the flow of data between Redis and your database
"""

import os
import json
import redis
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def connect_to_redis():
    """Connect to Redis using your app's configuration"""
    try:
        from dotenv import load_dotenv
        load_dotenv()

        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            r = redis.from_url(redis_url, decode_responses=True)
        else:
            r = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                password=os.getenv('REDIS_PASSWORD'),
                decode_responses=True
            )

        r.ping()
        logger.info("✅ Redis connection successful")
        return r

    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        return None


def check_supabase_connection():
    """Check Supabase connection"""
    try:
        from dotenv import load_dotenv
        load_dotenv()

        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')

        if not supabase_url or not supabase_key:
            logger.error("❌ Supabase credentials not found")
            return None

        # Try to import and connect to Supabase
        try:
            from supabase import create_client, Client
            supabase: Client = create_client(supabase_url, supabase_key)

            # Test connection with a simple query
            # This will fail gracefully if tables don't exist
            try:
                result = supabase.table('document_sessions').select('id').limit(1).execute()
                logger.info("✅ Supabase connection successful")
                return supabase
            except Exception as e:
                logger.info(f"✅ Supabase connected but tables may not exist: {e}")
                return supabase

        except ImportError:
            logger.warning("⚠️  Supabase client not installed. Install with: pip install supabase")
            return None

    except Exception as e:
        logger.error(f"❌ Supabase connection failed: {e}")
        return None


def analyze_redis_data_details(r: redis.Redis):
    """Analyze Redis data in detail"""
    print("\n" + "=" * 60)
    print("DETAILED REDIS DATA ANALYSIS")
    print("=" * 60)

    try:
        all_keys = r.keys('*')

        if not all_keys:
            print("❌ No data found in Redis")
            return {}

        data_summary = {}

        for key in all_keys:
            try:
                key_type = r.type(key)
                ttl = r.ttl(key)

                # Get the actual data
                if key_type == 'string':
                    raw_data = r.get(key)
                    try:
                        data = json.loads(raw_data) if raw_data else {}
                    except json.JSONDecodeError:
                        data = raw_data
                elif key_type == 'hash':
                    data = r.hgetall(key)
                else:
                    data = f"[{key_type} type - not analyzed]"

                # Categorize by prefix
                prefix = key.split(':')[0] if ':' in key else 'unknown'
                if prefix not in data_summary:
                    data_summary[prefix] = []

                # Extract session ID
                session_id = None
                if ':' in key:
                    potential_session = key.split(':', 1)[1]
                    if len(potential_session) > 10:  # Likely a session ID
                        session_id = potential_session

                ttl_status = "Permanent" if ttl == -1 else f"{ttl}s" if ttl > 0 else "Expired"

                entry = {
                    'key': key,
                    'session_id': session_id,
                    'type': key_type,
                    'ttl': ttl_status,
                    'data_preview': None
                }

                # Create a preview of the data
                if isinstance(data, dict):
                    if 'timestamp' in data:
                        entry['timestamp'] = data['timestamp']
                    if 'status' in data:
                        entry['status'] = data['status']
                    if 'original_filename' in data:
                        entry['filename'] = data['original_filename']

                    # Show key structure
                    entry['data_preview'] = f"Dict with keys: {list(data.keys())[:5]}"
                elif isinstance(data, str):
                    entry['data_preview'] = data[:100] + "..." if len(data) > 100 else data
                else:
                    entry['data_preview'] = str(data)[:100]

                data_summary[prefix].append(entry)

            except Exception as e:
                logger.error(f"Error analyzing key {key}: {e}")

        # Print organized summary
        for prefix, entries in data_summary.items():
            print(f"\n📁 {prefix.upper()} DATA ({len(entries)} entries):")
            print("-" * 50)

            for entry in entries[:10]:  # Show first 10 entries
                print(f"🔑 Key: {entry['key']}")
                if entry['session_id']:
                    print(f"   Session: {entry['session_id']}")
                if entry.get('timestamp'):
                    print(f"   Time: {entry['timestamp']}")
                if entry.get('status'):
                    print(f"   Status: {entry['status']}")
                if entry.get('filename'):
                    print(f"   File: {entry['filename']}")
                print(f"   TTL: {entry['ttl']}")
                print(f"   Data: {entry['data_preview']}")
                print()

        return data_summary

    except Exception as e:
        logger.error(f"Error in detailed analysis: {e}")
        return {}


def check_data_persistence_flow(r: redis.Redis, supabase=None):
    """Check how data flows from Redis to permanent storage"""
    print("\n" + "=" * 60)
    print("DATA PERSISTENCE FLOW ANALYSIS")
    print("=" * 60)

    # Get session IDs from Redis
    session_keys = r.keys('status:*') + r.keys('cleaned:*') + r.keys('summary:*')
    session_ids = set()

    for key in session_keys:
        if ':' in key:
            session_id = key.split(':', 1)[1]
            session_ids.add(session_id)

    print(f"📊 Found {len(session_ids)} unique sessions in Redis")

    for session_id in list(session_ids)[:5]:  # Check first 5 sessions
        print(f"\n🔍 Analyzing session: {session_id}")

        # Check what data exists in Redis for this session
        redis_data = {}
        for prefix in ['status', 'cleaned', 'summary', 'processing']:
            key = f"{prefix}:{session_id}"
            if r.exists(key):
                try:
                    raw_data = r.get(key)
                    if raw_data:
                        data = json.loads(raw_data)
                        redis_data[prefix] = data
                        print(f"   ✅ Redis {prefix}: {data.get('timestamp', 'No timestamp')}")
                except Exception as e:
                    print(f"   ❌ Redis {prefix}: Error reading - {e}")

        # Check if data exists in Supabase (if connected)
        if supabase:
            try:
                # Check common table names
                tables_to_check = ['document_sessions', 'processing_sessions', 'documents', 'sessions']

                for table_name in tables_to_check:
                    try:
                        result = supabase.table(table_name).select('*').eq('session_id', session_id).execute()
                        if result.data:
                            print(f"   ✅ Supabase {table_name}: {len(result.data)} record(s)")
                        else:
                            print(f"   ❌ Supabase {table_name}: No records")
                    except Exception as e:
                        print(f"   ⚠️  Supabase {table_name}: {str(e)[:50]}...")

            except Exception as e:
                print(f"   ❌ Supabase check failed: {e}")
        else:
            print("   ⚠️  Supabase not connected - cannot check database persistence")


def suggest_debugging_steps(redis_summary: Dict):
    """Suggest debugging steps based on findings"""
    print("\n" + "=" * 60)
    print("DEBUGGING RECOMMENDATIONS")
    print("=" * 60)

    total_keys = sum(len(entries) for entries in redis_summary.values())

    if total_keys == 0:
        print("❌ NO DATA IN REDIS")
        print("   • Your application is not storing data in Redis")
        print("   • Check if your app is actually calling the Redis store methods")
        print("   • Add logging to your Redis operations")

    elif 'status' in redis_summary and len(redis_summary['status']) > 0:
        print("✅ DATA IS BEING STORED IN REDIS")
        print("   • Redis operations are working correctly")
        print("   • Issue might be with data retrieval or display")
        print("\n📋 Next steps:")
        print("   1. Check your application's data retrieval logic")
        print("   2. Verify your frontend is calling the right API endpoints")
        print("   3. Check if data is being moved from Redis to Supabase")
        print("   4. Add logging to your data retrieval functions")

        # Show recent activity
        if 'status' in redis_summary:
            recent_entries = []
            for entry in redis_summary['status']:
                if entry.get('timestamp'):
                    recent_entries.append(entry)

            if recent_entries:
                print(f"\n🕒 RECENT ACTIVITY:")
                for entry in recent_entries[:3]:
                    print(f"   • {entry['key']}: {entry.get('timestamp', 'No timestamp')}")

    print(f"\n🔍 WHAT TO CHECK IN YOUR APPLICATION:")
    print("   1. Look for errors in your application logs")
    print("   2. Check if your API endpoints are returning the data")
    print("   3. Verify your frontend is making the correct API calls")
    print("   4. Check if data is being transferred from Redis to database")
    print("   5. Add debugging prints to your data retrieval functions")


def main():
    print("🔍 Data Flow Debugging Analysis")
    print("=" * 60)

    # Connect to systems
    r = connect_to_redis()
    if not r:
        print("Cannot proceed without Redis connection")
        return

    supabase = check_supabase_connection()

    # Analyze data
    redis_summary = analyze_redis_data_details(r)
    check_data_persistence_flow(r, supabase)
    suggest_debugging_steps(redis_summary)

    print(f"\n✅ Analysis complete!")
    print(f"💡 If you're still not seeing data in your application:")
    print(f"   1. Add print statements to your API endpoints")
    print(f"   2. Check browser developer tools for API errors")
    print(f"   3. Verify your frontend is calling the correct endpoints")


if __name__ == "__main__":
    main()