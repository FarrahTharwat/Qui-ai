#!/usr/bin/env python3
"""
Enhanced API Debug Script - Diagnose FastAPI timeout issues
"""

import requests
import json
import sys
import time
import threading
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"


def print_separator(title):
    print(f"\n{'=' * 50}")
    print(f"{title}")
    print(f"{'=' * 50}")


def test_endpoint_with_timeout(endpoint, method="GET", data=None, files=None, timeout=5):
    """Test an endpoint with custom timeout and timing"""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n🔍 Testing: {method} {url}")

    start_time = time.time()

    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=timeout)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, files=files, timeout=timeout)

        end_time = time.time()
        duration = end_time - start_time

        print(f"✅ Response Time: {duration:.2f} seconds")
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")

        # Try to parse JSON response
        try:
            json_response = response.json()
            print(f"JSON Response: {json.dumps(json_response, indent=2)}")
        except:
            print(f"Raw Response: {response.text[:500]}...")

        return response

    except requests.exceptions.Timeout:
        end_time = time.time()
        duration = end_time - start_time
        print(f"⏰ TIMEOUT after {duration:.2f} seconds (limit: {timeout}s)")
        return None
    except requests.exceptions.RequestException as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"❌ Request failed after {duration:.2f} seconds: {e}")
        return None


def check_database_connections():
    """Check if database connections are causing delays"""
    print_separator("DATABASE CONNECTION DIAGNOSTICS")

    # Test health endpoint timing
    print("Testing health endpoint timing...")
    start = time.time()
    response = requests.get(f"{BASE_URL}/health", timeout=10)
    duration = time.time() - start
    print(f"Health check took: {duration:.2f} seconds")

    if response.status_code == 200:
        health_data = response.json()
        print("Service status:")
        for service, status in health_data.get("services", {}).items():
            print(f"  {service}: {status}")


def test_problematic_endpoints():
    """Test the endpoints that are timing out with different approaches"""
    print_separator("PROBLEMATIC ENDPOINTS DIAGNOSIS")

    # Test documents endpoint with short timeout
    print("\n1. Testing /documents endpoint with 3s timeout:")
    test_endpoint_with_timeout("/documents", timeout=3)

    # Test status endpoint with short timeout
    print("\n2. Testing /status endpoint with 3s timeout:")
    test_endpoint_with_timeout("/status/test-session", timeout=3)

    # Test with even shorter timeout to see if it's immediate hang
    print("\n3. Testing /documents with 1s timeout:")
    test_endpoint_with_timeout("/documents", timeout=1)


def analyze_server_logs():
    """Provide guidance on checking server logs"""
    print_separator("SERVER LOG ANALYSIS GUIDE")
    print("""
When you check your FastAPI server terminal, look for:

1. DATABASE CONNECTION ERRORS:
   - Supabase connection timeouts
   - Redis connection hangs
   - SQL query timeout errors

2. PROCESSING ERRORS:
   - Infinite loops in document listing
   - Hanging database queries
   - Memory issues

3. DEPENDENCY INJECTION ISSUES:
   - get_document_service() hanging
   - Database manager initialization problems

4. COMMON PATTERNS:
   - "INFO: 127.0.0.1:XXXX - GET /api/v1/documents" (then nothing)
   - Error traceback mentioning database connections
   - Warnings about connection pools

IMMEDIATE FIXES TO TRY:
1. Restart your FastAPI server
2. Check if Supabase/Redis connections are stable
3. Add debug prints to document_service.list_documents()
4. Check for infinite loops in database queries
""")


def suggest_code_fixes():
    """Suggest specific code fixes based on the upload.py file"""
    print_separator("SPECIFIC CODE FIXES TO TRY")
    print("""
Based on your upload.py file, try these fixes:

1. ADD TIMEOUT TO DATABASE QUERIES:
   In your DocumentProcessingService.list_documents():
   ```python
   # Add query timeout
   documents = supabase.table('documents').select('*').limit(limit).offset(offset).execute(timeout=5)
   ```

2. ADD ERROR HANDLING TO /documents ENDPOINT:
   ```python
   @router.get("/documents")
   async def list_all_documents(...):
       try:
           # Add timeout here
           documents = await asyncio.wait_for(
               document_service.list_documents(limit, offset),
               timeout=5.0
           )
           # ... rest of code
       except asyncio.TimeoutError:
           return JSONResponse(
               status_code=504,
               content={"error": "Database query timeout"}
           )
   ```

3. ADD DEBUG LOGGING:
   Add this at the start of list_all_documents():
   ```python
   logger.info(f"Starting document listing with limit={limit}, offset={offset}")
   ```

4. CHECK REDIS MANAGER:
   Your get_session_status might be hanging on Redis operations.
   Add timeouts to Redis operations.

QUICK TEST:
Comment out the document_service.list_documents() call temporarily 
and return a dummy response to see if the timeout goes away.
""")


def main():
    print_separator("ENHANCED FASTAPI DEBUG TOOL")
    print(f"Time: {datetime.now()}")

    # Basic server check
    print_separator("SERVER STATUS CHECK")
    try:
        response = requests.get("http://localhost:8000", timeout=5)
        print(f"✅ Server responding: {response.status_code}")
    except:
        print("❌ Server not responding")
        return

    # Check database connections
    check_database_connections()

    # Test working endpoints first
    print_separator("WORKING ENDPOINTS")
    test_endpoint_with_timeout("/health", timeout=5)

    # Test problematic endpoints
    test_problematic_endpoints()

    # Provide analysis
    analyze_server_logs()
    suggest_code_fixes()

    print_separator("NEXT STEPS")
    print("""
1. Check your FastAPI server logs RIGHT NOW
2. Look for hanging requests or error messages
3. Try the code fixes suggested above
4. Restart your server and test again
5. If still hanging, add debug prints to isolate the issue

The timeout suggests your database queries are hanging or taking too long.
This is likely a Supabase query issue or infinite loop in your code.
""")


if __name__ == "__main__":
    main()