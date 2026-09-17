import os
import sys
import time
import json
import requests

# Ensure UTF-8 stdout encoding on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

API_PORT = int(os.environ.get("API_PORT", 5000))
BASE_URL = f"http://127.0.0.1:{API_PORT}"

def run_tests():
    print(f"[TEST] Starting synthetic test suite against API Sniffer at {BASE_URL}...")
    
    # 1. Test Health Check
    try:
        r = requests.get(f"{BASE_URL}/healthz", timeout=3)
        print(f"[OK] Healthcheck status: {r.status_code} - {r.json()}")
    except Exception as e:
        print(f"[FAIL] Healthcheck failed: {e}")
        return False

    # 2. Test GET with query parameters (including multi-value query arrays)
    print("\n[1/7] Sending GET request with query params...")
    r_get = requests.get(
        f"{BASE_URL}/api/v1/users",
        params={"page": "1", "limit": "20", "role": ["admin", "editor"], "search": "john doe"},
        headers={"X-Custom-Header": "TestGetValue", "User-Agent": "SnifferTestClient/1.0"}
    )
    print(f"GET Response: {r_get.status_code}")

    # 3. Test POST with JSON payload
    print("\n[2/7] Sending POST request with JSON payload...")
    r_post = requests.post(
        f"{BASE_URL}/api/v1/orders/create",
        json={
            "order_id": "ORD-99823",
            "amount": 149.99,
            "currency": "USD",
            "items": [{"sku": "ITEM-1", "qty": 2}, {"sku": "ITEM-2", "qty": 1}],
            "metadata": {"source": "mobile_app", "discount_code": None}
        },
        headers={"X-Device-OS": "iOS 17.2", "Authorization": "Bearer mock_token_12345"}
    )
    print(f"POST Response: {r_post.status_code}")

    # 4. Test PUT with raw text payload
    print("\n[3/7] Sending PUT request with raw payload...")
    r_put = requests.put(
        f"{BASE_URL}/api/v1/config/update",
        data="system_mode=maintenance&max_connections=500",
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    print(f"PUT Response: {r_put.status_code}")

    # 5. Test PATCH request
    print("\n[4/7] Sending PATCH request...")
    r_patch = requests.patch(
        f"{BASE_URL}/api/v1/users/104",
        json={"status": "active", "verified": True}
    )
    print(f"PATCH Response: {r_patch.status_code}")

    # 6. Test DELETE request
    print("\n[5/7] Sending DELETE request...")
    r_delete = requests.delete(
        f"{BASE_URL}/api/v1/products/8812",
        headers={"X-Reason": "discontinued"}
    )
    print(f"DELETE Response: {r_delete.status_code}")

    # 7. Test OPTIONS request
    print("\n[6/7] Sending OPTIONS request...")
    r_options = requests.options(
        f"{BASE_URL}/api/v1/cors-test",
        headers={"Access-Control-Request-Method": "POST", "Origin": "https://example.com"}
    )
    print(f"OPTIONS Response: {r_options.status_code}")

    # 8. Test Multipart File Upload
    print("\n[7/7] Sending POST with Multipart file upload...")
    test_file_path = "sample_test_file.txt"
    with open(test_file_path, "w", encoding="utf-8") as f:
        f.write("Hello World! This is a test file upload to the API Request Sniffer.\nTimestamp: " + str(time.time()))

    with open(test_file_path, "rb") as upload_f:
        r_file = requests.post(
            f"{BASE_URL}/api/v1/documents/upload",
            files={"document": ("sample_test_file.txt", upload_f, "text/plain")},
            data={"author": "Yuva", "category": "report"}
        )
    print(f"Multipart Upload Response: {r_file.status_code}")

    # Clean up local test file
    if os.path.exists(test_file_path):
        os.remove(test_file_path)

    print("\n[SUCCESS] All synthetic requests sent successfully!")
    return True

if __name__ == "__main__":
    run_tests()
