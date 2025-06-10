#!/usr/bin/env python3
"""
API Debug Script - Diagnose FastAPI endpoint issues
"""

import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"


def print_separator(title):
    print(f"\n{'=' * 50}")
    print(f"{title}")
    print(f"{'=' * 50}")


def test_endpoint(endpoint, method="GET", data=None, files=None):
    """Test an endpoint and show detailed response"""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n🔍 Testing: {method} {url}")

    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, files=files, timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")

        # Try to parse JSON response
        try:
            json_response = response.json()
            print(f"JSON Response: {json.dumps(json_response, indent=2)}")
        except:
            print(f"Raw Response: {response.text[:500]}...")

        return response

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None


def check_server_status():
    """Check if server is responding at all"""
    try:
        response = requests.get("http://localhost:8000", timeout=5)
        print(f"✅ Server is responding on port 8000")
        print(f"Response: {response.status_code}")
        return True
    except:
        print(f"❌ Server not responding on port 8000")
        return False


def main():
    print_separator("FastAPI Debug Tool")
    print(f"Time: {datetime.now()}")

    # Check if server is running
    print_separator("SERVER STATUS CHECK")
    if not check_server_status():
        print("Please start your FastAPI server first:")
        print("uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        sys.exit(1)

    # Test root endpoint
    print_separator("ROOT ENDPOINT TEST")
    test_endpoint("")

    # Test OpenAPI docs
    print_separator("DOCS ENDPOINT TEST")
    docs_response = requests.get("http://localhost:8000/docs")
    print(f"Docs available: {docs_response.status_code == 200}")

    # Test health endpoint with detailed output
    print_separator("HEALTH ENDPOINT DETAILED TEST")
    health_response = test_endpoint("/health")

    # Test documents endpoint
    print_separator("DOCUMENTS ENDPOINT DETAILED TEST")
    docs_response = test_endpoint("/documents")

    # Test status endpoint with fake session
    print_separator("STATUS ENDPOINT TEST")
    status_response = test_endpoint("/status/fake-session-id")

    # Check what endpoints are available
    print_separator("AVAILABLE ENDPOINTS")
    try:
        openapi_response = requests.get("http://localhost:8000/openapi.json")
        if openapi_response.status_code == 200:
            openapi_data = openapi_response.json()
            paths = openapi_data.get("paths", {})
            print("Available endpoints:")
            for path, methods in paths.items():
                for method in methods.keys():
                    print(f"  {method.upper()} {path}")
        else:
            print("Could not retrieve OpenAPI schema")
    except Exception as e:
        print(f"Error getting endpoints: {e}")

    # Server logs suggestion
    print_separator("DEBUGGING SUGGESTIONS")
    print("1. Check your FastAPI server terminal for error messages")
    print("2. Verify your database connection is working")
    print("3. Check if Redis is running (if you're using it)")
    print("4. Look at the server logs for specific error details")
    print("5. Make sure all required environment variables are set")
    print("\nServer terminal should show detailed error information.")


if __name__ == "__main__":
    main()