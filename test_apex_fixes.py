#!/usr/bin/env python3
"""
Test script to verify the Oracle APEX integration fixes
Run this after starting the Flask app to test the updated implementation
"""

import requests
import json
from datetime import date

# Flask app URL
BASE_URL = "http://127.0.0.1:5000"

def test_apex_integration():
    """Test the updated Oracle APEX integration."""
    
    print("Testing Updated Oracle APEX Integration")
    print("=" * 50)
    print("Make sure your Flask app is running with:")
    print("  cd 'c:\\Users\\Sange\\APEX App\\ifs_client'")
    print("  .\\env\\Scripts\\python.exe app.py")
    print("=" * 50)
    
    # Test GET bookings endpoint
    print("\n1. Testing GET bookings endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/bookings/1", timeout=5)
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ GET bookings endpoint working")
        else:
            print(f"   ❌ GET bookings failed with status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("   ❌ Could not connect to Flask app")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test POST return endpoint
    print("\n2. Testing POST return endpoint...")
    try:
        test_data = {
            "empid": 1,
            "bookid": 123,
            "returndate": date.today().isoformat()
        }
        response = requests.post(
            f"{BASE_URL}/do_return",
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.json()}")
        if response.status_code in [200, 500]:  # 200 for success, 500 for APEX errors
            print("   ✅ POST return endpoint working")
        else:
            print(f"   ❌ POST return failed with status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("   ❌ Could not connect to Flask app")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test dashboard endpoint
    print("\n3. Testing dashboard endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/dashboard/1", timeout=5)
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Dashboard endpoint working")
        else:
            print(f"   ❌ Dashboard failed with status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("   ❌ Could not connect to Flask app")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("Test completed!")
    print("\nCheck the Flask app console for detailed logging:")
    print("- 'Calling APEX GET: ...' - Shows GET requests to Oracle APEX")
    print("- 'Calling APEX POST: ...' - Shows POST requests to Oracle APEX")
    print("- 'APEX Response URL: ...' - Shows the exact response URL")
    print("- 'APEX Response Status: ...' - Shows HTTP status codes")
    print("- Error messages for timeouts, connection issues, etc.")

if __name__ == "__main__":
    test_apex_integration()
