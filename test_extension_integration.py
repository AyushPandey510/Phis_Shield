#!/usr/bin/env python3
"""
Test script to verify Chrome extension integration with PhisGuard backend.
This simulates the API calls that the extension background script makes.
"""

import requests
import json
import time

# API configuration
API_BASE = 'http://localhost:5001'
API_KEY = 'a0c674401be58be8eb1929239742b625'

def test_api_call(endpoint, data, description):
    """Test an API call and return the result."""
    url = f"{API_BASE}{endpoint}"
    headers = {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY
    }

    try:
        print(f"\n🧪 Testing {description}...")
        print(f"   URL: {url}")
        print(f"   Data: {json.dumps(data, indent=2)}")

        start_time = time.time()
        response = requests.post(url, json=data, headers=headers, timeout=30)
        end_time = time.time()

        print(f"   Status: {response.status_code}")
        print(".2f")
        if response.status_code == 200:
            result = response.json()
            print("   ✅ Success")
            return True, result
        else:
            print(f"   ❌ Failed: {response.text}")
            return False, None

    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False, None

def main():
    print("🔍 PhisGuard Chrome Extension Integration Test")
    print("=" * 50)

    # Test cases that simulate extension functionality
    test_cases = [
        {
            'endpoint': '/check-url',
            'data': {'url': 'https://google.com'},
            'description': 'URL Security Check (simulates link scanning)'
        },
        {
            'endpoint': '/comprehensive-check',
            'data': {'url': 'https://google.com'},
            'description': 'Comprehensive Security Analysis (simulates page analysis)'
        },
        {
            'endpoint': '/check-ssl',
            'data': {'url': 'https://google.com'},
            'description': 'SSL Certificate Check'
        },
        {
            'endpoint': '/expand-link',
            'data': {'url': 'https://google.com'},
            'description': 'Link Expansion Check'
        },
        {
            'endpoint': '/check-breach',
            'data': {'password': 'testpassword123'},
            'description': 'Password Breach Check'
        }
    ]

    results = []
    for test_case in test_cases:
        success, result = test_api_call(
            test_case['endpoint'],
            test_case['data'],
            test_case['description']
        )
        results.append((test_case['description'], success))

    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)

    passed = 0
    total = len(results)

    for description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {description}")
        if success:
            passed += 1

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All extension integration tests PASSED!")
        print("The Chrome extension should work correctly with the backend.")
    else:
        print("⚠️  Some tests failed. Check the backend configuration.")

if __name__ == '__main__':
    main()