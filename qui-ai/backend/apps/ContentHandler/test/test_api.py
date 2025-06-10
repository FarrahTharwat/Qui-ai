# test_api.py
"""Test script for the document processing API"""

import requests
import time
import json
from pathlib import Path

# API base URL
BASE_URL = "http://localhost:8000/api/v1"


def test_upload_and_process(pdf_file_path: str):
    """Test the complete upload and processing workflow"""

    print(f"Testing upload and processing for: {pdf_file_path}")

    # 1. Upload file
    print("\n1. Uploading file...")
    with open(pdf_file_path, 'rb') as f:
        files = {'file': (Path(pdf_file_path).name, f, 'application/pdf')}
        response = requests.post(f"{BASE_URL}/upload", files=files)

    if response.status_code != 202:
        print(f"Upload failed: {response.status_code} - {response.text}")
        return None

    upload_result = response.json()
    session_id = upload_result['session_id']
    print(f"✓ Upload successful! Session ID: {session_id}")
    print(f"Status endpoint: {upload_result['status_endpoint']}")

    # 2. Monitor processing status
    print("\n2. Monitoring processing status...")
    max_attempts = 60  # 5 minutes max
    attempt = 0

    while attempt < max_attempts:
        response = requests.get(f"{BASE_URL}/status/{session_id}")

        if response.status_code != 200:
            print(f"Status check failed: {response.status_code}")
            break

        status_result = response.json()
        current_status = status_result.get('status', 'unknown')

        print(f"Status: {current_status}")

        if current_status == 'completed':
            print("✓ Processing completed successfully!")
            document_id = status_result.get('document_id')
            print(f"Document ID: {document_id}")
            break
        elif current_status == 'failed':
            print("✗ Processing failed!")
            print(f"Error: {status_result.get('metadata', {}).get('error', 'Unknown error')}")
            return None

        time.sleep(5)  # Wait 5 seconds before next check
        attempt += 1

    if attempt >= max_attempts:
        print("⚠ Processing timeout - check manually")
        return session_id

    # 3. Retrieve processed document
    print("\n3. Retrieving processed document...")
    response = requests.get(f"{BASE_URL}/document/{session_id}")

    if response.status_code != 200:
        print(f"Document retrieval failed: {response.status_code}")
        return session_id

    document_result = response.json()
    document = document_result['document']

    print("✓ Document retrieved successfully!")
    print(f"Pages processed: {len(document.get('summarized_pages', []))}")
    print(f"Combined summary length: {len(document.get('combined_summary', ''))}")

    # Save result to file for inspection
    output_file = f"test_result_{session_id}.json"
    with open(output_file, 'w') as f:
        json.dump(document, f, indent=2)
    print(f"Full result saved to: {output_file}")

    return session_id


def test_api_endpoints():
    """Test all API endpoints"""

    print("Testing API endpoints...")

    # Test health check
    print("\n1. Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 200:
        print("✓ Health check passed")
        print(f"Services: {response.json().get('services', {})}")
    else:
        print(f"✗ Health check failed: {response.status_code}")

    # Test document listing
    print("\n2. Testing document listing...")
    response = requests.get(f"{BASE_URL}/documents?limit=10")
    if response.status_code == 200:
        result = response.json()
        print(f"✓ Document listing successful")
        print(f"Found {len(result.get('documents', []))} documents")
    else:
        print(f"✗ Document listing failed: {response.status_code}")

    # Test invalid session status
    print("\n3. Testing invalid session status...")
    response = requests.get(f"{BASE_URL}/status/invalid-session-id")
    if response.status_code == 404:
        print("✓ Invalid session correctly handled")
    else:
        print(f"✗ Invalid session not handled properly: {response.status_code}")


def benchmark_processing(pdf_file_path: str, num_tests: int = 3):
    """Benchmark the processing performance"""

    print(f"\nBenchmarking with {num_tests} tests...")
    times = []

    for i in range(num_tests):
        print(f"\nTest {i + 1}/{num_tests}")
        start_time = time.time()

        session_id = test_upload_and_process(pdf_file_path)
        if session_id:
            processing_time = time.time() - start_time
            times.append(processing_time)
            print(f"Processing time: {processing_time:.2f} seconds")
        else:
            print(f"Test {i + 1} failed")

    if times:
        avg_time = sum(times) / len(times)
        print(f"\nBenchmark Results:")
        print(f"Average processing time: {avg_time:.2f} seconds")
        print(f"Min time: {min(times):.2f} seconds")
        print(f"Max time: {max(times):.2f} seconds")


def upload_example():
    """Example of how to use the upload API"""

    # Using requests library
    pdf_file = "example.pdf"

    # Upload file
    with open(pdf_file, 'rb') as f:
        files = {'file': (pdf_file, f, 'application/pdf')}
        response = requests.post("http://localhost:8000/api/v1/upload", files=files)

    if response.status_code == 202:
        result = response.json()
        session_id = result['session_id']
        print(f"Upload successful! Session ID: {session_id}")

        # Monitor status
        while True:
            status_response = requests.get(f"http://localhost:8000/api/v1/status/{session_id}")
            status = status_response.json()['status']

            if status == 'completed':
                # Get processed document
                doc_response = requests.get(f"http://localhost:8000/api/v1/document/{session_id}")
                document = doc_response.json()['document']
                print("Processing completed!")
                break
            elif status == 'failed':
                print("Processing failed!")
                break

            time.sleep(5)  # Wait 5 seconds


def curl_examples():
    """Print cURL command examples"""

    examples = """
    # Upload a PDF file
    curl -X POST "http://localhost:8000/api/v1/upload" \\
         -H "accept: application/json" \\
         -H "Content-Type: multipart/form-data" \\
         -F "file=@example.pdf"

    # Check processing status
    curl -X GET "http://localhost:8000/api/v1/status/{session_id}" \\
         -H "accept: application/json"

    # Get processed document
    curl -X GET "http://localhost:8000/api/v1/document/{session_id}" \\
         -H "accept: application/json"

    # List all documents
    curl -X GET "http://localhost:8000/api/v1/documents?limit=10" \\
         -H "accept: application/json"

    # Health check
    curl -X GET "http://localhost:8000/api/v1/health" \\
         -H "accept: application/json"
    """

    print("cURL Examples:")
    print(examples)


def main():
    """Main test function"""

    print("Document Processing API Test Suite")
    print("=" * 40)

    # Test basic endpoints
    test_api_endpoints()

    # Print curl examples
    print("\n" + "=" * 40)
    curl_examples()

    # If a test PDF file exists, run upload test
    test_files = ["example.pdf", "test.pdf", "sample.pdf"]
    test_file = None

    for file in test_files:
        if Path(file).exists():
            test_file = file
            break

    if test_file:
        print(f"\n{'=' * 40}")
        print(f"Found test file: {test_file}")

        # Run single test
        session_id = test_upload_and_process(test_file)

        if session_id:
            # Run benchmark if test was successful
            run_benchmark = input("\nRun benchmark tests? (y/n): ").lower() == 'y'
            if run_benchmark:
                benchmark_processing(test_file, 3)
    else:
        print(
            "\nNo test PDF file found. Place a PDF file named 'example.pdf', 'test.pdf', or 'sample.pdf' in the current directory to run upload tests.")


if __name__ == "__main__":
    main()