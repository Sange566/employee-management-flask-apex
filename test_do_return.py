#!/usr/bin/env python3
"""
Test script for the /do_return endpoint
Run this after starting the Flask app to test the new endpoint
"""

import requests
import json
from datetime import date

# Flask app URL
BASE_URL = "http://127.0.0.1:5000"

def test_do_return():
    """Test the /do_return endpoint with various scenarios."""
    
    print("Testing /do_return endpoint...")
    print("=" * 50)
    
    # Test data
    test_cases = [
        {
            "name": "Valid return request",
            "data": {
                "empid": 1,
                "bookid": 123,
                "returndate": date.today().isoformat()
            },
            "expected_status": 200
        },
        {
            "name": "Missing empid",
            "data": {
                "bookid": 123,
                "returndate": date.today().isoformat()
            },
            "expected_status": 400
        },
        {
            "name": "Non-numeric empid",
            "data": {
                "empid": "abc",
                "bookid": 123,
                "returndate": date.today().isoformat()
            },
            "expected_status": 400
        },
        {
            "name": "Invalid date format",
            "data": {
                "empid": 1,
                "bookid": 123,
                "returndate": "2025-13-45"  # Invalid date
            },
            "expected_status": 400
        },
        {
            "name": "Mock: Already returned (bookid=999)",
            "data": {
                "empid": 1,
                "bookid": 999,
                "returndate": date.today().isoformat()
            },
            "expected_status": 200
        },
        {
            "name": "Mock: Error scenario (bookid=888)",
            "data": {
                "empid": 1,
                "bookid": 888,
                "returndate": date.today().isoformat()
            },
            "expected_status": 500
        }
    ]
    
    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        print(f"Data: {test_case['data']}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/do_return",
                json=test_case['data'],
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.json()}")
            
            if response.status_code == test_case['expected_status']:
                print("✅ PASS")
            else:
                print(f"❌ FAIL - Expected {test_case['expected_status']}, got {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("❌ FAIL - Could not connect to Flask app. Make sure it's running on http://127.0.0.1:5000")
        except Exception as e:
            print(f"❌ FAIL - Error: {e}")
    
    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    test_do_return()
