#!/usr/bin/env python3
"""
PhisGuard API Testing Script
Tests all implemented endpoints to ensure they work correctly.
"""

import requests
import json
import time

BASE_URL = "http://localhost:5001"

def test_endpoint(name, method, endpoint, data=None, expected_status=200):
    """Test a single API endpoint"""
    print(f"\n🧪 Testing {name}...")

    headers = {"Content-Type": "application/json"}
    # Add API key for protected endpoints
    if endpoint not in ["/health", "/"]:
        headers["X-API-Key"] = "dev-api-key-change-this-in-production-1234567890123456"

    try:
        if method.upper() == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=10)
        else:
            response = requests.post(
                f"{BASE_URL}{endpoint}",
                json=data,
                headers=headers,
                timeout=10
            )
        
        if response.status_code == expected_status:
            print(f"✅ {name}: SUCCESS ({response.status_code})")
            if response.content:
                try:
                    result = response.json()
                    print(f"   Response: {json.dumps(result, indent=2)[:200]}...")
                except:
                    print(f"   Response: {response.text[:200]}...")
            return True
        else:
            print(f"❌ {name}: FAILED ({response.status_code})")
            print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ {name}: ERROR - {str(e)}")
        return False

def main():
    print("🚀 PhisGuard API Testing Suite")
    print("=" * 50)
    
    # Wait a moment for server to be ready
    time.sleep(1)
    
    tests_passed = 0
    total_tests = 0
    
    # Test basic endpoints
    total_tests += 1
    if test_endpoint("Health Check", "GET", "/health"):
        tests_passed += 1
    
    total_tests += 1
    if test_endpoint("Root Endpoint", "GET", "/"):
        tests_passed += 1
    
    # Test URL checking
    total_tests += 1
    if test_endpoint("URL Check - Safe", "POST", "/check-url", 
                    {"url": "https://github.com"}):
        tests_passed += 1
    
    total_tests += 1
    if test_endpoint("URL Check - Suspicious", "POST", "/check-url", 
                    {"url": "http://httpforever.com/"}):
        tests_passed += 1
    
    # Test comprehensive check
    total_tests += 1
    if test_endpoint("Comprehensive Check", "POST", "/comprehensive-check", 
                    {"url": "https://example.com"}):
        tests_passed += 1
    
    # Test email text analysis
    total_tests += 1
    if test_endpoint("Email Text Analysis", "POST", "/check-email-text", 
                    {"subject": "Test Subject", "body": "This is a test email body"}):
        tests_passed += 1
    
    # Test SSL check
    total_tests += 1
    if test_endpoint("SSL Check", "POST", "/check-ssl", 
                    {"url": "https://github.com"}):
        tests_passed += 1
    
    # Test link expansion
    total_tests += 1
    if test_endpoint("Link Expansion", "POST", "/expand-link", 
                    {"url": "https://github.com"}):
        tests_passed += 1
    
    # Test breach check
    total_tests += 1
    if test_endpoint("Breach Check", "POST", "/check-breach", 
                    {"email": "test@example.com"}):
        tests_passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! PhisGuard is ready for use.")
    else:
        print(f"⚠️  {total_tests - tests_passed} tests failed. Check the implementation.")
    
    print("\n🔗 Next Steps:")
    print("1. Load the Chrome extension in developer mode")
    print("2. Visit websites to test auto-scanning")
    print("3. Click 'Details' buttons on links")
    print("4. Test admin dashboard at http://localhost:5001/admin/")
    print("5. Try Gmail integration if available")

if __name__ == "__main__":
    main()
