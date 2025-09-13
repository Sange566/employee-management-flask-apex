#!/usr/bin/env python3
"""
Test script for the improved Oracle APEX integration
Run this after starting the Flask app to test the enhanced error handling and logging
"""

import requests
import json
from datetime import date

# Flask app URL
BASE_URL = "http://127.0.0.1:5000"

def test_get_bookings():
    """Test the GET bookings endpoint with various scenarios."""
    
    print("Testing GET bookings endpoint...")
    print("=" * 50)
    
    test_cases = [
        {
            "name": "Valid employee ID",
            "empid": "1",
            "expected_status": 200
        },
        {
            "name": "Non-numeric employee ID",
            "empid": "abc",
            "expected_status": 302  # Redirect due to validation error
        },
        {
            "name": "Empty employee ID",
            "empid": "",
            "expected_status": 404  # Route not found
        }
    ]
    
    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        print(f"Employee ID: {test_case['empid']}")
        
        try:
            if test_case['empid']:
                url = f"{BASE_URL}/bookings/{test_case['empid']}"
            else:
                url = f"{BASE_URL}/bookings/"
            
            response = requests.get(url, timeout=5)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == test_case['expected_status']:
                print("✅ PASS")
            else:
                print(f"❌ FAIL - Expected {test_case['expected_status']}, got {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("❌ FAIL - Could not connect to Flask app. Make sure it's running on http://127.0.0.1:5000")
        except Exception as e:
            print(f"❌ FAIL - Error: {e}")

def test_post_return():
    """Test the POST return endpoint with various scenarios."""
    
    print("\n\nTesting POST return endpoint...")
    print("=" * 50)
    
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

def test_dashboard():
    """Test the dashboard endpoint."""
    
    print("\n\nTesting dashboard endpoint...")
    print("=" * 50)
    
    test_cases = [
        {
            "name": "Valid employee ID",
            "empid": "1",
            "expected_status": 200
        },
        {
            "name": "Non-numeric employee ID",
            "empid": "xyz",
            "expected_status": 302  # Redirect due to validation error
        }
    ]
    
    for test_case in test_cases:
        print(f"\nTest: {test_case['name']}")
        print(f"Employee ID: {test_case['empid']}")
        
        try:
            response = requests.get(f"{BASE_URL}/dashboard/{test_case['empid']}", timeout=5)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == test_case['expected_status']:
                print("✅ PASS")
            else:
                print(f"❌ FAIL - Expected {test_case['expected_status']}, got {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("❌ FAIL - Could not connect to Flask app. Make sure it's running on http://127.0.0.1:5000")
        except Exception as e:
            print(f"❌ FAIL - Error: {e}")

def main():
    """Run all tests."""
    print("Oracle APEX Integration Test Suite")
    print("=" * 60)
    print("Make sure your Flask app is running with:")
    print("  cd 'c:\\Users\\Sange\\APEX App\\ifs_client'")
    print("  .\\env\\Scripts\\python.exe app.py")
    print("=" * 60)
    
    test_get_bookings()
    test_post_return()
    test_dashboard()
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("\nCheck the Flask app console for detailed APEX URL logging:")
    print("- 'Calling APEX URL: ...' - Shows the exact URL being called")
    print("- 'APEX Response URL: ...' - Shows the actual response URL")
    print("- 'APEX Response Status: ...' - Shows the HTTP status code")
    print("- 'APEX Timeout/Connection/HTTP Error: ...' - Shows specific error types")

if __name__ == "__main__":
    main()
