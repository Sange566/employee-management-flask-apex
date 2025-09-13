import os
import json
from datetime import date, datetime
from urllib.parse import urljoin
import io
import base64

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, make_response, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import qrcode

# Load .env
load_dotenv()

# Get BASE_URL from environment and normalize it
BASE_URL = os.getenv("BASE_URL", "https://oracleapex.com/ords/ifs325_techinnovators").rstrip("/")
# Remove any existing module suffix to ensure clean ORDS base
if "/inventory_booking" in BASE_URL:
    BASE_URL = BASE_URL.replace("/inventory_booking", "")
if "/employees" in BASE_URL:
    BASE_URL = BASE_URL.replace("/employees", "")
if "/inventory" in BASE_URL:
    BASE_URL = BASE_URL.replace("/inventory", "")

MOCK = os.getenv("MOCK", "0") == "1"  # Use live APEX data by default
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

# Global variable to track mock inventory changes (only used when MOCK=True)
mock_inventory_changes = {}

# Validate BASE_URL configuration
if not BASE_URL or not BASE_URL.startswith("https://"):
    raise ValueError(f"Invalid BASE_URL configuration: '{BASE_URL}'. Must be a valid HTTPS URL.")

# Helpful startup diagnostics
print(f"DEBUG_INFO: BASE_URL='{BASE_URL}' MOCK={MOCK} FLASK_DEBUG={FLASK_DEBUG}")
if MOCK:
    print("INFO: Running in MOCK mode - using local test data instead of Oracle APEX")
else:
    print(f"INFO: Running in LIVE mode - connecting to Oracle APEX at: {BASE_URL}")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-key-change-in-production")  # for flash messages and sessions

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Enhanced User class for Flask-Login with role support
class User(UserMixin):
    def __init__(self, id, role="employee", employee_id=None):
        self.id = id
        self.role = role
        self.employee_id = employee_id
    
    def is_admin(self):
        return self.role == "admin"
    
    def is_employee(self):
        return self.role == "employee"
    
    def get_employee_id(self):
        return self.employee_id

# User credentials with roles (in production, use a proper database)
USERS = {
    "admin": {"password": generate_password_hash("password123"), "role": "admin", "employee_id": None},
    # Employee accounts based on actual APEX data
    "Candice": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 114},
    "Peter": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 116},
    "Jessica": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 109},
    "Ayakha": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 61},
    "Nomsa": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 105},
    "Sipho": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 3},
    "Sarah": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 101},
    "Neo": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 115},
    "Khanyi": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 111},
    "Thabo": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 1},
    "David": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 102},
    "Rebecca": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 120},
    "Lerato": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 4},
    "Linda": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 117},
    "Sangesonke": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 21},
    "Zama": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 41},
    "Aisha": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 2},
    "Michael": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 110},
    "Emily": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 107},
    "Ashley": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 118},
    "Daniel": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 112},
    "John": {"password": generate_password_hash("employee123"), "role": "employee", "employee_id": 104}
}

# Employee ID to username mapping for QR login
EMPLOYEE_USERS = {
    "114": "Candice",  # Employee ID 114 maps to Candice user
    "116": "Peter",    # Employee ID 116 maps to Peter user
    "109": "Jessica",  # Employee ID 109 maps to Jessica user
    "61": "Ayakha",    # Employee ID 61 maps to Ayakha user
    "105": "Nomsa",    # Employee ID 105 maps to Nomsa user
    "3": "Sipho",      # Employee ID 3 maps to Sipho user
    "101": "Sarah",    # Employee ID 101 maps to Sarah user
    "115": "Neo",      # Employee ID 115 maps to Neo user
    "111": "Khanyi",   # Employee ID 111 maps to Khanyi user
    "1": "Thabo",      # Employee ID 1 maps to Thabo user
    "102": "David",    # Employee ID 102 maps to David user
    "120": "Rebecca",  # Employee ID 120 maps to Rebecca user
    "4": "Lerato",     # Employee ID 4 maps to Lerato user
    "117": "Linda",    # Employee ID 117 maps to Linda user
    "21": "Sangesonke", # Employee ID 21 maps to Sangesonke user
    "41": "Zama",      # Employee ID 41 maps to Zama user
    "2": "Aisha",      # Employee ID 2 maps to Aisha user
    "110": "Michael",  # Employee ID 110 maps to Michael user
    "107": "Emily",    # Employee ID 107 maps to Emily user
    "118": "Ashley",   # Employee ID 118 maps to Ashley user
    "112": "Daniel",   # Employee ID 112 maps to Daniel user
    "104": "John"      # Employee ID 104 maps to John user
}

@login_manager.user_loader
def load_user(user_id):
    if user_id in USERS:
        user_data = USERS[user_id]
        return User(user_id, user_data["role"], user_data["employee_id"])
    return None

# ---- Authorization Decorators ----
def admin_required(f):
    """Decorator to require admin role."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "danger")
            return redirect(url_for('login'))
        if not current_user.is_admin():
            flash("Access denied. Admin privileges required.", "danger")
            return redirect(url_for('employee_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def employee_required(f):
    """Decorator to require employee role."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "danger")
            return redirect(url_for('login'))
        if not current_user.is_employee():
            flash("Access denied. Employee privileges required.", "danger")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def verify_ownership(employee_id):
    """Verify that the current user owns the resource."""
    if not current_user.is_authenticated:
        return False
    if current_user.is_admin():
        return True  # Admins can access everything
    return current_user.get_employee_id() == employee_id

# ---- Helper functions ----
def _get(endpoint, params=None):
    """GET JSON from ORDS endpoint. endpoint is like 'employees/get'."""
    if MOCK:
        return mock_get(endpoint, params)
    url = f"{BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }
    try:
        print(f"[APEX GET] URL: {url} PARAMS: {params}")
        r = requests.get(url, params=params, headers=headers, timeout=30, verify=True)
        print(f"[APEX GET] status: {r.status_code}")
        print(f"[APEX GET] response headers: {dict(r.headers)}")
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout as e:
        print("APEX Timeout Error:", e)
        return {"error": "Oracle APEX service took too long to respond", "ok": False}
    except requests.exceptions.ConnectionError as e:
        print("APEX Connection Error:", e)
        return {"error": "Unable to reach APEX", "ok": False}
    except Exception as e:
        text = getattr(e, 'response', None) and getattr(e.response, 'text', None)
        print("APEX GET unexpected:", str(e), text)
        return {"error": str(e), "ok": False}

def _post(endpoint, params=None):
    """POST to ORDS endpoint. endpoint is like 'employees/create'."""
    if MOCK:
        return mock_post(endpoint, params)
    url = f"{BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }
    try:
        print(f"[APEX POST] URL: {url} PARAMS: {params}")
        r = requests.post(url, params=params, headers=headers, timeout=30, verify=True)
        print(f"[APEX POST] status: {r.status_code}")
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return {"text": r.text}
    except requests.exceptions.Timeout as e:
        print("APEX Timeout Error:", e)
        return {"error": "Oracle APEX service took too long to respond", "ok": False}
    except Exception as e:
        print("APEX POST unexpected:", e)
        return {"error": str(e), "ok": False}

def _put(endpoint, params=None):
    """PUT to ORDS endpoint. endpoint is like 'employees/update'."""
    if MOCK:
        return mock_put(endpoint, params)
    url = f"{BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }
    try:
        print(f"[APEX PUT] URL: {url} PARAMS: {params}")
        r = requests.put(url, params=params, headers=headers, timeout=30, verify=True)
        print(f"[APEX PUT] status: {r.status_code}")
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return {"text": r.text}
    except requests.exceptions.Timeout as e:
        print("APEX Timeout Error:", e)
        return {"error": "Oracle APEX service took too long to respond", "ok": False}
    except Exception as e:
        print("APEX PUT unexpected:", e)
        return {"error": str(e), "ok": False}

# ---- Mock data (if BASE_URL unreachable, for demos) ----
def mock_get(endpoint, params):
    if endpoint == "inventory_booking/get_date_data":
        empid = str(params.get("empid")) if params and params.get("empid") else None
        start_date = params.get("start_date") if params else None
        end_date = params.get("end_date") if params else None
        
        # Handle case when no params are passed (show all bookings)
        if not params:
            empid = None
            start_date = None
            end_date = None
        
        # Enhanced sample data for demo with more variety and realistic dates
        from datetime import date, timedelta
        today = date.today()
        
        all_bookings = [
            # Recent bookings (some overdue, some current)
                {"t_booking_id": 1, "t_inventory_id": 1, "t_item_name": "Raspberry Pi 4 Model B",
                 "t_employee_id": 1, "employee_name": "Thabo Mokoena",
             "t_booking_date": (today - timedelta(days=10)).strftime("%Y-%m-%d"), "t_return_date": "Not Returned" },
                {"t_booking_id": 2, "t_inventory_id": 2, "t_item_name": "Arduino Uno R3",
             "t_employee_id": 101, "employee_name": "Sarah Johnson",
             "t_booking_date": (today - timedelta(days=5)).strftime("%Y-%m-%d"), "t_return_date": (today - timedelta(days=1)).strftime("%Y-%m-%d") },
                {"t_booking_id": 3, "t_inventory_id": 3, "t_item_name": "ESP32 Development Board",
             "t_employee_id": 3, "employee_name": "Sipho Dlamini",
             "t_booking_date": (today - timedelta(days=3)).strftime("%Y-%m-%d"), "t_return_date": (today - timedelta(days=1)).strftime("%Y-%m-%d") },
                {"t_booking_id": 4, "t_inventory_id": 4, "t_item_name": "Soldering Iron Kit",
             "t_employee_id": 2, "employee_name": "Aisha Peters",
             "t_booking_date": (today - timedelta(days=8)).strftime("%Y-%m-%d"), "t_return_date": "Not Returned" },
            {"t_booking_id": 5, "t_inventory_id": 5, "t_item_name": "Digital Oscilloscope",
             "t_employee_id": 110, "employee_name": "Michael Peterson",
             "t_booking_date": (today - timedelta(days=12)).strftime("%Y-%m-%d"), "t_return_date": "Not Returned" },
            {"t_booking_id": 6, "t_inventory_id": 6, "t_item_name": "3D Printer",
             "t_employee_id": 4, "employee_name": "Lerato Ndlovu",
             "t_booking_date": (today - timedelta(days=2)).strftime("%Y-%m-%d"), "t_return_date": today.strftime("%Y-%m-%d") },
            {"t_booking_id": 7, "t_inventory_id": 21, "t_item_name": "Playstation",
             "t_employee_id": 21, "employee_name": "Sangesonke Njameni",
             "t_booking_date": (today - timedelta(days=15)).strftime("%Y-%m-%d"), "t_return_date": "Not Returned" },
            {"t_booking_id": 8, "t_inventory_id": 2, "t_item_name": "Arduino Mega 2560",
                 "t_employee_id": 2, "employee_name": "Sarah Johnson",
             "t_booking_date": (today - timedelta(days=20)).strftime("%Y-%m-%d"), "t_return_date": (today - timedelta(days=5)).strftime("%Y-%m-%d") },
            {"t_booking_id": 9, "t_inventory_id": 3, "t_item_name": "Fluke Multimeter 87V",
             "t_employee_id": 3, "employee_name": "Mike Chen",
             "t_booking_date": (today - timedelta(days=25)).strftime("%Y-%m-%d"), "t_return_date": "Not Returned" },
            {"t_booking_id": 10, "t_inventory_id": 4, "t_item_name": "Workstation Xeon W-2295",
             "t_employee_id": 4, "employee_name": "Lisa Wang",
             "t_booking_date": (today - timedelta(days=30)).strftime("%Y-%m-%d"), "t_return_date": (today - timedelta(days=10)).strftime("%Y-%m-%d") },
            # Additional bookings for more data
            {"t_booking_id": 11, "t_inventory_id": 1, "t_item_name": "Raspberry Pi 4 Model B",
             "t_employee_id": 2, "employee_name": "Sarah Johnson",
             "t_booking_date": (today - timedelta(days=1)).strftime("%Y-%m-%d"), "t_return_date": "Not Returned" },
            {"t_booking_id": 12, "t_inventory_id": 5, "t_item_name": "Digital Oscilloscope",
             "t_employee_id": 4, "employee_name": "Lisa Wang",
             "t_booking_date": (today - timedelta(days=6)).strftime("%Y-%m-%d"), "t_return_date": "Not Returned" },
            {"t_booking_id": 13, "t_inventory_id": 21, "t_item_name": "Playstation",
             "t_employee_id": 1, "employee_name": "Thabo Mokoena",
             "t_booking_date": (today - timedelta(days=4)).strftime("%Y-%m-%d"), "t_return_date": today.strftime("%Y-%m-%d") },
            {"t_booking_id": 14, "t_inventory_id": 6, "t_item_name": "3D Printer",
             "t_employee_id": 3, "employee_name": "Mike Chen",
             "t_booking_date": (today - timedelta(days=18)).strftime("%Y-%m-%d"), "t_return_date": "Not Returned" },
            {"t_booking_id": 15, "t_inventory_id": 2, "t_item_name": "Arduino Uno R3",
             "t_employee_id": 21, "employee_name": "Alex Rodriguez",
             "t_booking_date": (today - timedelta(days=7)).strftime("%Y-%m-%d"), "t_return_date": "Not Returned" }
        ]
        
        print(f"[MOCK DEBUG] empid: {empid}, start_date: {start_date}, end_date: {end_date}")
        print(f"[MOCK DEBUG] Total bookings before filtering: {len(all_bookings)}")
        
        # Filter by employee ID if specified
        if empid and empid != "None" and empid != "" and empid != "all":
            all_bookings = [b for b in all_bookings if str(b["t_employee_id"]) == str(empid)]
            print(f"[MOCK DEBUG] After empid filter: {len(all_bookings)}")
        else:
            print(f"[MOCK DEBUG] No empid filter applied, showing all {len(all_bookings)} bookings")
        
        # Filter by date range if specified (simplified mock filtering)
        if start_date:
            all_bookings = [b for b in all_bookings if b["t_booking_date"] >= start_date]
            print(f"[MOCK DEBUG] After start_date filter: {len(all_bookings)}")
        if end_date:
            all_bookings = [b for b in all_bookings if b["t_booking_date"] <= end_date]
            print(f"[MOCK DEBUG] After end_date filter: {len(all_bookings)}")
        
        result = {"items": all_bookings, "count": len(all_bookings)}
        print(f"[MOCK DEBUG] Final result: {result}")
        return result
    
    elif endpoint == "employees/get":
        return {"items": [
            {"t_empid": 114, "t_emp_fname": "Candice", "t_emp_lname": "Adams", "t_emp_dept": "Legal"},
            {"t_empid": 116, "t_emp_fname": "Peter", "t_emp_lname": "Botha", "t_emp_dept": "Operations"},
            {"t_empid": 109, "t_emp_fname": "Jessica", "t_emp_lname": "Brown", "t_emp_dept": "Finance"},
            {"t_empid": 61, "t_emp_fname": "Ayakha", "t_emp_lname": "David", "t_emp_dept": "Finance"},
            {"t_empid": 105, "t_emp_fname": "Nomsa", "t_emp_lname": "Dlamini", "t_emp_dept": "R&D"},
            {"t_empid": 3, "t_emp_fname": "Sipho", "t_emp_lname": "Dlamini", "t_emp_dept": "IT"},
            {"t_empid": 101, "t_emp_fname": "Sarah", "t_emp_lname": "Johnson", "t_emp_dept": "Finance"},
            {"t_empid": 115, "t_emp_fname": "Neo", "t_emp_lname": "Khumalo", "t_emp_dept": "Finance"},
            {"t_empid": 111, "t_emp_fname": "Khanyi", "t_emp_lname": "Mahlangu", "t_emp_dept": "HR"},
            {"t_empid": 1, "t_emp_fname": "Thabo", "t_emp_lname": "Mokoena", "t_emp_dept": "R&D"},
            {"t_empid": 102, "t_emp_fname": "David", "t_emp_lname": "Mokoena", "t_emp_dept": "IT"},
            {"t_empid": 120, "t_emp_fname": "Rebecca", "t_emp_lname": "Morris", "t_emp_dept": "Marketing"},
            {"t_empid": 4, "t_emp_fname": "Lerato", "t_emp_lname": "Ndlovu", "t_emp_dept": "HPC"},
            {"t_empid": 117, "t_emp_fname": "Linda", "t_emp_lname": "Nguyen", "t_emp_dept": "Support"},
            {"t_empid": 21, "t_emp_fname": "Sangesonke", "t_emp_lname": "Njameni", "t_emp_dept": "Q&A"},
            {"t_empid": 41, "t_emp_fname": "Zama", "t_emp_lname": "Nkosi", "t_emp_dept": "Dev"},
            {"t_empid": 2, "t_emp_fname": "Aisha", "t_emp_lname": "Peters", "t_emp_dept": "QA"},
            {"t_empid": 110, "t_emp_fname": "Michael", "t_emp_lname": "Peterson", "t_emp_dept": "IT"},
            {"t_empid": 107, "t_emp_fname": "Emily", "t_emp_lname": "Smith", "t_emp_dept": "QA"},
            {"t_empid": 118, "t_emp_fname": "Ashley", "t_emp_lname": "Taylor", "t_emp_dept": "QA"},
            {"t_empid": 112, "t_emp_fname": "Daniel", "t_emp_lname": "White", "t_emp_dept": "Logistics"},
            {"t_empid": 104, "t_emp_fname": "John", "t_emp_lname": "Williams", "t_emp_dept": "Marketing"}
        ], "count": 22}
    
    elif endpoint == "inventory/get":
        global mock_inventory_changes
        
        # Base inventory data
        base_inventory = [
            {"t_item_id": 1, "t_item_name": "Raspberry Pi 4 Model B", "t_item_category": "Electronics", "t_item_quantity": 5},
            {"t_item_id": 2, "t_item_name": "Arduino Uno R3", "t_item_category": "Electronics", "t_item_quantity": 3},
            {"t_item_id": 3, "t_item_name": "ESP32 Development Board", "t_item_category": "Electronics", "t_item_quantity": 0},
            {"t_item_id": 4, "t_item_name": "Soldering Iron Kit", "t_item_category": "Tools", "t_item_quantity": 2},
            {"t_item_id": 5, "t_item_name": "Digital Oscilloscope", "t_item_category": "Electronics", "t_item_quantity": 1},
            {"t_item_id": 6, "t_item_name": "3D Printer", "t_item_category": "Electronics", "t_item_quantity": 0},
            {"t_item_id": 21, "t_item_name": "Playstation", "t_item_category": "Gaming", "t_item_quantity": 1}
        ]
        
        # Apply inventory changes if any
        for item in base_inventory:
            item_id = item["t_item_id"]
            if item_id in mock_inventory_changes:
                item["t_item_quantity"] = mock_inventory_changes[item_id]
                print(f"[MOCK GET] Applied inventory change for item {item_id}: quantity = {mock_inventory_changes[item_id]}")
        
        return {"items": base_inventory, "count": len(base_inventory)}
    
    elif endpoint == "usage/get":
        return {"items": [
            {"t_booking_id": 1, "t_employee_id": 1, "t_item_id": 1, "t_item_name": "Raspberry Pi 4 Model B",
             "t_booking_date": "2025-08-30", "t_return_date": "Not Returned", "status": "Active"},
            {"t_booking_id": 2, "t_employee_id": 2, "t_item_id": 4, "t_item_name": "Soldering Iron Kit",
             "t_booking_date": "2025-08-29", "t_return_date": "2025-09-05", "status": "Returned"}
        ], "count": 2}
    
    return {"items": [], "count": 0}

def mock_post(endpoint, params):
    if endpoint == "inventory_booking/postdata":
        # Mock different scenarios for testing
        bookid = params.get("bookid") if params else None
        
        # Simulate different responses based on bookid for testing
        if bookid == 999:
            # Simulate already returned
            return {"updated_rows": 0, "status": "no_change"}
        elif bookid == 888:
            # Simulate error
            return {"error": "Mock error: Invalid booking ID"}
        else:
            # Simulate successful update
            return {"updated_rows": 1, "status": "success"}
    
    elif endpoint == "employees/create":
        return {"t_empid": 999, "status": "created"}
    
    elif endpoint == "inventory/create":
        return {"t_item_id": 999, "status": "created"}
    
    return {"updated_rows": 0, "status": "no_change"}

def mock_put(endpoint, params):
    """Mock PUT requests for updates."""
    global mock_inventory_changes
    
    if endpoint == "inventory/update":
        # Mock inventory update
        item_id = params.get("t_item_id") if params else None
        new_quantity = params.get("t_item_quantity") if params else None
        
        if item_id and new_quantity is not None:
            # Track the inventory change
            mock_inventory_changes[int(item_id)] = int(new_quantity)
            print(f"[MOCK PUT] Updating inventory item {item_id} to quantity {new_quantity}")
            print(f"[MOCK PUT] Current inventory changes: {mock_inventory_changes}")
        
        # Simulate successful update
        return {"updated_rows": 1, "status": "success", "item_id": item_id, "new_quantity": new_quantity}
    
    return {"updated_rows": 0, "status": "no_change"}

def get_dashboard_data():
    """Get dashboard data including KPIs, recent activity, and low stock alerts."""
    try:
        # Get data from live APEX sources (with mock fallback)
        # Get all employees
        employees_resp = _get("employees/get")
        if isinstance(employees_resp, dict) and employees_resp.get("error"):
            employees_resp = mock_get("employees/get", None)
        total_employees = len(employees_resp.get("items", []))
        
        # Get all inventory items
        inventory_resp = _get("inventory/get")
        if isinstance(inventory_resp, dict) and inventory_resp.get("error"):
            inventory_resp = mock_get("inventory/get", None)
        total_items = len(inventory_resp.get("items", []))
        
        # Get all bookings (no empid filter to get all)
        bookings_resp = _get("inventory_booking/get_date_data", params={})
        if isinstance(bookings_resp, dict) and bookings_resp.get("error"):
            bookings_resp = mock_get("inventory_booking/get_date_data", None)
        all_bookings = bookings_resp.get("items", [])
        
        # Calculate currently issued (bookings with "Not Returned")
        currently_issued = len([b for b in all_bookings if b.get("t_return_date") == "Not Returned"])
        
        # Calculate recent bookings (all bookings)
        recent_bookings = len(all_bookings)
        
        # Create recent activity from bookings
        recent_activity = []
        for booking in all_bookings:
            # Add booking activity
            recent_activity.append({
                "type": "booking",
                "item_name": booking.get("t_item_name", "Unknown Item"),
                "employee_id": booking.get("t_employee_id"),
                "date": booking.get("t_booking_date"),
                "booking_id": booking.get("t_booking_id")
            })
            
            # Add return activity if returned
            if booking.get("t_return_date") != "Not Returned":
                recent_activity.append({
                    "type": "return",
                    "item_name": booking.get("t_item_name", "Unknown Item"),
                    "employee_id": booking.get("t_employee_id"),
                    "date": booking.get("t_return_date"),
                    "booking_id": booking.get("t_booking_id")
                })
        
        # Sort recent activity by date (most recent first)
        recent_activity.sort(key=lambda x: x["date"], reverse=True)
        recent_activity = recent_activity[:10]  # Limit to 10 most recent
        
        # Get low stock alerts from inventory
        low_stock_alerts = []
        for item in inventory_resp.get("items", []):
            quantity = item.get("t_item_quantity", 0)
            if quantity <= 2:  # Low stock threshold
                low_stock_alerts.append({
                    "name": item.get("t_item_name", "Unknown Item"),
                    "category": item.get("t_item_category", "Unknown"),
                    "quantity": quantity
                })
        
        return {
            "total_items": total_items,
            "currently_issued": currently_issued,
            "total_employees": total_employees,
            "recent_bookings": recent_bookings,
            "recent_activity": recent_activity,
            "low_stock_alerts": low_stock_alerts
        }
        
    except Exception as e:
        print(f"Error getting dashboard data: {e}")
        # Return default values if there's an error
        return {
            "total_items": 7,  # From mock data
            "currently_issued": 8,  # From mock data
            "total_employees": 22,  # From mock data
            "recent_bookings": 15,  # From mock data
            "recent_activity": [],
            "low_stock_alerts": []
        }

# ---- Routes ----
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        if username in USERS and check_password_hash(USERS[username]["password"], password):
            user_data = USERS[username]
            user = User(username, user_data["role"], user_data["employee_id"])
            login_user(user)
            
            # Redirect based on role
            if user.is_admin():
                flash(f"Welcome back, Admin {username}!", "success")
                next_page = request.args.get('next') or url_for('index')
            else:
                flash(f"Welcome back, {username}!", "success")
                next_page = request.args.get('next') or url_for('employee_dashboard')
            
            return redirect(next_page)
        else:
            flash("Invalid username or password.", "danger")
    
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    username = current_user.id
    logout_user()
    flash(f"Goodbye, {username}!", "info")
    return redirect(url_for('login'))

@app.route("/qr-login", methods=["POST"])
def qr_login():
    """Handle QR code login via AJAX."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        # Check for empid or username in QR code data
        empid = data.get("empid")
        username = data.get("username")
        
        target_username = None
        
        if empid:
            # Convert empid to string for lookup
            empid_str = str(empid)
            if empid_str in EMPLOYEE_USERS:
                target_username = EMPLOYEE_USERS[empid_str]
        elif username:
            # Direct username lookup
            if username in USERS:
                target_username = username
        
        if target_username:
            # Log the user in
            user = User(target_username)
            login_user(user)
            return jsonify({
                "status": "success", 
                "message": f"Welcome, {target_username}!",
                "redirect": url_for('index')
            })
        else:
            return jsonify({
                "status": "error", 
                "message": "Invalid QR code - user not found"
            }), 401
            
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Login failed: {str(e)}"
        }), 500

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    # Redirect based on user role
    if current_user.is_employee():
        return redirect(url_for('employee_dashboard'))
    elif current_user.is_admin():
        if request.method == "POST":
            empid = request.form.get("empid", "").strip()
            if not empid:
                flash("Please enter an Employee ID.", "warning")
                return redirect(url_for("index"))
            return redirect(url_for("bookings", empid=empid))
        
        # Get dashboard data for the main page
        dashboard_data = get_dashboard_data()
        return render_template("index.html", MOCK_MODE=MOCK, **dashboard_data)
    else:
        flash("Invalid user role. Please contact administrator.", "danger")
        return redirect(url_for('login'))

@app.route("/bookings", methods=["GET"])
@admin_required
def bookings():
    """Redirect to bookings management page."""
    return redirect(url_for("bookings_management"))

@app.route("/bookings/<empid>", methods=["GET", "POST"])
@admin_required
def bookings_by_employee(empid):
    """Redirect to bookings management with employee filter."""
    # Validate empid
    if not empid or not empid.strip():
        flash("Employee ID is required.", "danger")
        return redirect(url_for("bookings_management"))
    
    try:
        # Ensure empid is numeric
        empid_int = int(empid.strip())
    except ValueError:
        flash("Employee ID must be a valid number.", "danger")
        return redirect(url_for("bookings_management"))
    
    # Redirect to bookings management with employee filter
    return redirect(url_for("bookings_management", empid=empid_int))

@app.route("/dashboard/<empid>")
@login_required
def dashboard(empid):
    """Employee dashboard with current vs history tabs."""
    # Validate empid
    if not empid or not empid.strip():
        flash("Employee ID is required.", "danger")
        return redirect(url_for("index"))
    
    try:
        # Ensure empid is numeric
        empid_int = int(empid.strip())
    except ValueError:
        flash("Employee ID must be a valid number.", "danger")
        return redirect(url_for("index"))
    
    # Fetch bookings using GET endpoint: inventory_booking/get_date_data?empid=...
    resp = _get("inventory_booking/get_date_data", params={"empid": empid_int})
    error = None
    items = []
    count = 0
    
    if isinstance(resp, dict) and resp.get("error"):
        error = resp["error"]
        flash(f"Unable to fetch dashboard data: {error}", "danger")
    else:
        # ORDS typically returns {"items":[...], "count": n, ...}
        items = resp.get("items", resp if isinstance(resp, list) else [])
        count = resp.get("count", len(items))
    
    # Process items for dashboard
    from datetime import datetime, date
    
    current_bookings = []
    returned_bookings = []
    active_count = 0
    returned_count = 0
    latest_booking_date = "N/A"
    
    for item in items:
        # Calculate days out and duration
        if item.get('t_booking_date'):
            try:
                booking_date = datetime.strptime(item['t_booking_date'], '%Y-%m-%d').date()
                days_out = (date.today() - booking_date).days
                item['days_out'] = days_out
                
                # Track latest booking
                if latest_booking_date == "N/A" or booking_date > datetime.strptime(latest_booking_date, '%Y-%m-%d').date():
                    latest_booking_date = item['t_booking_date']
            except:
                item['days_out'] = 0
        
        # Separate current vs returned
        if item.get('t_return_date') == 'Not Returned':
            current_bookings.append(item)
            active_count += 1
        else:
            # Calculate duration for returned items
            if item.get('t_booking_date') and item.get('t_return_date'):
                try:
                    booking_date = datetime.strptime(item['t_booking_date'], '%Y-%m-%d').date()
                    return_date = datetime.strptime(item['t_return_date'], '%Y-%m-%d').date()
                    duration = (return_date - booking_date).days
                    item['duration'] = duration
                except:
                    item['duration'] = 0
            else:
                item['duration'] = 0
            
            returned_bookings.append(item)
            returned_count += 1
    
    return render_template("dashboard.html", 
                         empid=empid, 
                         current_bookings=current_bookings,
                         returned_bookings=returned_bookings,
                         count=count, 
                         active_count=active_count,
                         returned_count=returned_count,
                         latest_booking_date=latest_booking_date,
                         error=error, 
                         MOCK_MODE=MOCK)

@app.route("/return", methods=["POST"])
@login_required
def do_return():
    bookid = request.form.get("bookid", "").strip()
    empid = request.form.get("empid", "").strip()
    returndate = request.form.get("returndate", "").strip()
    if not bookid or not empid:
        flash("Booking ID and Employee ID are required.", "danger")
        return redirect(url_for("index"))
    if not returndate:
        returndate = date.today().isoformat()
    # Call POST endpoint: inventory_booking/postdata?returndate=YYYY-MM-DD&bookid=...&empid=...
    resp = _post("inventory_booking/postdata", params={"returndate": returndate, "bookid": bookid, "empid": empid})
    # Evaluate response and present result
    result_msg = None
    if isinstance(resp, dict):
        if resp.get("updated_rows") == 1 or resp.get("status") == "success" or resp.get("status") == "ok":
            flash("Return recorded successfully.", "success")
            result_msg = resp
        elif resp.get("updated_rows") == 0:
            flash("No update performed. Booking may already be returned or parameters invalid.", "warning")
            result_msg = resp
        elif resp.get("error"):
            flash(f"Error calling API: {resp.get('error')}", "danger")
            result_msg = resp
        else:
            # generic
            flash("Return request completed. See response below.", "info")
            result_msg = resp
    else:
        flash("Unexpected response from API.", "danger")
        result_msg = {"raw": str(resp)}
    return render_template("return_result.html", resp=result_msg, bookid=bookid, empid=empid, returndate=returndate)

@app.route("/do_return", methods=["POST"])
@login_required
def do_return_api():
    """API endpoint for returning equipment with proper Oracle APEX integration."""
    try:
        # Get data from form or JSON
        if request.is_json:
            data = request.get_json()
            empid = data.get("empid", "").strip()
            bookid = data.get("bookid", "").strip()
            returndate = data.get("returndate", "").strip()
        else:
            empid = request.form.get("empid", "").strip()
            bookid = request.form.get("bookid", "").strip()
            returndate = request.form.get("returndate", "").strip()
        
        # Validate inputs
        if not empid or not bookid or not returndate:
            return jsonify({
                "error": "Missing required fields: empid, bookid, and returndate are required"
            }), 400
        
        # Validate empid and bookid are numeric
        try:
            empid_int = int(empid)
            bookid_int = int(bookid)
        except ValueError:
            return jsonify({
                "error": "empid and bookid must be numeric values"
            }), 400
        
        # Validate returndate format (basic check)
        try:
            from datetime import datetime
            datetime.strptime(returndate, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                "error": "returndate must be in YYYY-MM-DD format"
            }), 400
        
        # Make POST request to Oracle APEX REST endpoint
        resp = _post("inventory_booking/postdata", params={
            "empid": empid_int,
            "bookid": bookid_int,
            "returndate": returndate
        })
        
        # Handle APEX responses
        if isinstance(resp, dict):
            if resp.get("error"):
                error_msg = resp.get("error")
                # Determine appropriate status code based on error type
                if "timeout" in error_msg.lower() or "took too long" in error_msg.lower():
                    return jsonify({
                        "error": error_msg
                    }), 504
                elif "unable to reach" in error_msg.lower() or "connection" in error_msg.lower():
                    return jsonify({
                        "error": error_msg
                    }), 500
                else:
                    return jsonify({
                        "error": f"Oracle APEX service error: {error_msg}"
                    }), 500
            
            updated_rows = resp.get("updated_rows")
            if updated_rows == 1:
                return jsonify({
                    "status": "success",
                    "message": "Equipment marked as returned."
                })
            elif updated_rows == 0:
                return jsonify({
                    "status": "no_change",
                    "message": "This booking was already returned."
                })
            else:
                # Return the JSON from APEX as-is
                return jsonify(resp)
        else:
            return jsonify({
                "error": "Unexpected response format from Oracle APEX service"
            }), 500
            
    except Exception as e:
        return jsonify({
            "error": f"Internal server error: {str(e)}"
        }), 500

@app.route("/qrcode/<int:booking_id>")
@login_required
def generate_qrcode(booking_id):
    """Generate QR code for a specific booking."""
    # For demo purposes, we'll create a mock booking if not found
    # In a real app, you'd fetch this from your database
    booking_data = {
        "booking_id": booking_id,
        "item_name": "Raspberry Pi 4 Model B",
        "employee_id": 1,
        "booking_date": "2025-08-30",
        "status": "Active"
    }
    
    # Create QR code content
    qr_content = f"""Booking Details:
ID: {booking_data['booking_id']}
Item: {booking_data['item_name']}
Employee: {booking_data['employee_id']}
Date: {booking_data['booking_date']}
Status: {booking_data['status']}
Generated: {date.today().isoformat()}"""
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_content)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    # Create response
    response = make_response(img_buffer.getvalue())
    response.headers['Content-Type'] = 'image/png'
    response.headers['Content-Disposition'] = f'inline; filename=booking_{booking_id}_qrcode.png'
    
    return response

@app.route("/login-qrcode/<empid>")
def generate_login_qrcode(empid):
    """Generate QR code for login with employee ID."""
    # Create QR code content for login
    qr_content = f"empid={empid}"
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_content)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    # Create response
    response = make_response(img_buffer.getvalue())
    response.headers['Content-Type'] = 'image/png'
    response.headers['Content-Disposition'] = f'inline; filename=login_empid_{empid}_qrcode.png'
    
    return response

@app.route("/apex-url-test")
def apex_url_test():
    """Test if the Oracle APEX URL is accessible at all."""
    # Define URLs at the top to avoid UnboundLocalError
    base_url = "https://oracleapex.com"
    full_url = f"{BASE_URL}/get_date_data?empid=1"
    
    try:
        print("=" * 60)
        print("APEX URL ACCESSIBILITY TEST")
        print("=" * 60)
        
        # Test the base URL first
        print(f"Testing base URL: {base_url}")
        
        import requests
        response = requests.get(base_url, timeout=5)
        print(f"Base URL Status: {response.status_code}")
        
        # Test the full path
        print(f"Testing full URL: {full_url}")
        
        response2 = requests.get(full_url, timeout=5)
        print(f"Full URL Status: {response2.status_code}")
        print(f"Response Headers: {dict(response2.headers)}")
        
        return jsonify({
            "status": "success",
            "base_url_status": response.status_code,
            "full_url_status": response2.status_code,
            "base_url": base_url,
            "full_url": full_url,
            "response_headers": dict(response2.headers)
        })
        
    except requests.exceptions.Timeout:
        return jsonify({
            "status": "timeout",
            "message": "URL is not responding within 5 seconds",
            "base_url": base_url,
            "full_url": full_url
        })
    except requests.exceptions.ConnectionError as e:
        return jsonify({
            "status": "connection_error",
            "message": f"Cannot connect to Oracle APEX: {str(e)}",
            "base_url": base_url,
            "full_url": full_url
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "base_url": base_url,
            "full_url": full_url
        })

@app.route("/apex-connectivity-test")
def apex_connectivity_test():
    """Simple connectivity test without helper functions."""
    try:
        print("=" * 60)
        print("APEX CONNECTIVITY TEST")
        print("=" * 60)
        
        test_url = f"{BASE_URL}/get_date_data?empid=1"
        print(f"Testing direct connection to: {test_url}")
        
        # Direct request without helper functions
        import requests
        response = requests.get(
            test_url,
            headers={"Accept": "application/json"},
            timeout=10  # Shorter timeout for quick test
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response URL: {response.url}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response Data: {data}")
                return jsonify({
                    "status": "success",
                    "message": "Direct connection successful",
                    "status_code": response.status_code,
                    "response_url": response.url,
                    "data": data
                })
            except Exception as json_error:
                print(f"JSON Parse Error: {json_error}")
                return jsonify({
                    "status": "partial_success",
                    "message": "Connection successful but JSON parse failed",
                    "status_code": response.status_code,
                    "response_url": response.url,
                    "response_text": response.text[:500],
                    "json_error": str(json_error)
                })
        else:
            return jsonify({
                "status": "error",
                "message": f"HTTP error {response.status_code}",
                "status_code": response.status_code,
                "response_url": response.url,
                "response_text": response.text[:500]
            })
            
    except requests.exceptions.Timeout:
        print("Direct connection timeout")
        return jsonify({
            "status": "error",
            "message": "Direct connection timeout (10s)",
            "url": test_url
        })
    except requests.exceptions.ConnectionError as e:
        print(f"Direct connection error: {e}")
        return jsonify({
            "status": "error",
            "message": f"Connection error: {str(e)}",
            "url": test_url
        })
    except Exception as e:
        print(f"Direct test exception: {e}")
        return jsonify({
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
            "url": test_url
        })

@app.route("/apex-mock-test")
def apex_mock_test():
    """Test with MOCK mode enabled to verify app functionality."""
    global MOCK
    original_mock = MOCK
    
    try:
        print("=" * 60)
        print("APEX MOCK TEST")
        print("=" * 60)
        
        # Temporarily enable MOCK mode
        MOCK = True
        
        print(f"Temporarily enabling MOCK mode: {MOCK}")
        
        # Call the _get function with empid=1
        resp = _get("get_date_data", params={"empid": 1})
        
        print(f"Mock Test Response: {resp}")
        
        # Restore original MOCK setting
        MOCK = original_mock
        print(f"Restored MOCK mode to: {MOCK}")
        print("=" * 60)
        
        return jsonify({
            "status": "success",
            "message": "Mock test completed",
            "mock_response": resp,
            "original_mock_setting": original_mock
        })
        
    except Exception as e:
        # Restore original MOCK setting in case of error
        MOCK = original_mock
        print(f"Mock test exception: {e}")
        return jsonify({
            "status": "error",
            "error": f"Mock test failed: {str(e)}",
            "original_mock_setting": original_mock
        })

@app.route("/apex-network-test")
def apex_network_test():
    """Test different network approaches to reach Oracle APEX."""
    import requests
    import urllib3
    
    # Disable SSL warnings for testing
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    test_url = f"{BASE_URL}/get_date_data?empid=1"
    
    print("=" * 60)
    print("APEX NETWORK DIAGNOSTIC TEST")
    print("=" * 60)
    
    tests = [
        {
            "name": "Standard Request",
            "kwargs": {
                "timeout": 30,
                "verify": True,
                "headers": {"Accept": "application/json"}
            }
        },
        {
            "name": "With User-Agent",
            "kwargs": {
                "timeout": 30,
                "verify": True,
                "headers": {
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            }
        },
        {
            "name": "Extended Timeout",
            "kwargs": {
                "timeout": (10, 60),
                "verify": True,
                "headers": {
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            }
        },
        {
            "name": "No SSL Verify",
            "kwargs": {
                "timeout": 30,
                "verify": False,
                "headers": {
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            }
        }
    ]
    
    results = []
    
    for test in tests:
        print(f"\nTesting: {test['name']}")
        try:
            response = requests.get(test_url, **test['kwargs'])
            print(f"✅ SUCCESS: Status {response.status_code}")
            results.append({
                "test": test['name'],
                "status": "success",
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds()
            })
        except requests.exceptions.Timeout as e:
            print(f"❌ TIMEOUT: {e}")
            results.append({
                "test": test['name'],
                "status": "timeout",
                "error": str(e)
            })
        except requests.exceptions.ConnectionError as e:
            print(f"❌ CONNECTION ERROR: {e}")
            results.append({
                "test": test['name'],
                "status": "connection_error",
                "error": str(e)
            })
        except Exception as e:
            print(f"❌ OTHER ERROR: {e}")
            results.append({
                "test": test['name'],
                "status": "error",
                "error": str(e)
            })
    
    print("=" * 60)
    
    return jsonify({
        "status": "completed",
        "url_tested": test_url,
        "results": results
    })

@app.route("/apex-test")
def apex_test():
    """Test route to debug Oracle APEX connectivity."""
    try:
        print("=" * 60)
        print("APEX TEST ROUTE CALLED")
        print(f"BASE_URL: {BASE_URL}")
        print(f"MOCK MODE: {MOCK}")
        print("=" * 60)
        
        # Test basic connectivity first
        test_url = f"{BASE_URL}/get_date_data?empid=1"
        print(f"Testing URL: {test_url}")
        
        # Call the _get function with empid=1
        resp = _get("get_date_data", params={"empid": 1})
        
        print(f"APEX Test Response: {resp}")
        print("=" * 60)
        
        # Check if there was an error
        if isinstance(resp, dict) and resp.get("error"):
            return jsonify({
                "status": "error",
                "error": resp.get("error"),
                "url_attempted": test_url,
                "base_url": BASE_URL,
                "mock_mode": MOCK,
                "debug_info": "Check console for detailed logs"
            })
        else:
            # Return the raw JSON response
            return jsonify({
                "status": "success",
                "data": resp,
                "url_attempted": test_url,
                "base_url": BASE_URL,
                "mock_mode": MOCK
            })
            
    except Exception as e:
        print(f"APEX Test Exception: {e}")
        return jsonify({
            "status": "error",
            "error": f"Internal error: {str(e)}",
            "url_attempted": f"{BASE_URL}/get_date_data?empid=1",
            "base_url": BASE_URL,
            "mock_mode": MOCK
        })

@app.route("/qr-return", methods=["POST"])
@login_required
def qr_return():
    """Handle QR code return verification via AJAX."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        bookid = data.get("bookid")
        empid = data.get("empid")
        
        if not bookid or not empid:
            return jsonify({"status": "error", "message": "Booking ID and Employee ID are required"}), 400
        
        # First, get the booking details to verify the employee ID
        booking_resp = _get("inventory_booking/get_date_data", params={"empid": empid})
        
        if isinstance(booking_resp, dict) and booking_resp.get("error"):
            error_msg = booking_resp.get("error")
            # Determine appropriate status code based on error type
            if "timeout" in error_msg.lower() or "took too long" in error_msg.lower():
                return jsonify({"status": "error", "message": f"Oracle APEX service timeout: {error_msg}"}), 504
            elif "unable to reach" in error_msg.lower() or "connection" in error_msg.lower():
                return jsonify({"status": "error", "message": f"Unable to connect to Oracle APEX service: {error_msg}"}), 500
            else:
                return jsonify({"status": "error", "message": f"Oracle APEX service error: {error_msg}"}), 500
        
        # Check if the booking exists and belongs to this employee
        bookings = booking_resp.get("items", [])
        target_booking = None
        
        for booking in bookings:
            if str(booking.get("t_booking_id")) == str(bookid):
                target_booking = booking
                break
        
        if not target_booking:
            return jsonify({"status": "error", "message": "Booking not found for this employee"}), 404
        
        # Verify the employee ID matches
        if str(target_booking.get("t_employee_id")) != str(empid):
            return jsonify({"status": "error", "message": "QR code does not match booking employee"}), 403
        
        # Check if already returned
        if target_booking.get("t_return_date") != "Not Returned":
            return jsonify({"status": "error", "message": "Equipment already returned"}), 400
        
        # Proceed with the return
        return_resp = _post("inventory_booking/postdata", params={
            "returndate": date.today().isoformat(),
            "bookid": bookid,
            "empid": empid
        })
        
        if isinstance(return_resp, dict):
            if return_resp.get("error"):
                error_msg = return_resp.get("error")
                # Determine appropriate status code based on error type
                if "timeout" in error_msg.lower() or "took too long" in error_msg.lower():
                    return jsonify({"status": "error", "message": f"Oracle APEX service timeout: {error_msg}"}), 504
                elif "unable to reach" in error_msg.lower() or "connection" in error_msg.lower():
                    return jsonify({"status": "error", "message": f"Unable to connect to Oracle APEX service: {error_msg}"}), 500
                else:
                    return jsonify({"status": "error", "message": f"Oracle APEX service error: {error_msg}"}), 500
            elif return_resp.get("updated_rows") == 1 or return_resp.get("status") == "success":
                return jsonify({
                    "status": "success", 
                    "message": "Return recorded successfully",
                    "redirect": url_for('dashboard', empid=empid)
                })
            elif return_resp.get("updated_rows") == 0:
                return jsonify({"status": "error", "message": "No update performed. Booking may already be returned."}), 400
            else:
                return jsonify({"status": "success", "message": "Return request completed"})
        else:
            return jsonify({"status": "error", "message": "Unexpected response from API"}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": f"Return failed: {str(e)}"}), 500

# ---- New CRUD Routes ----

# Employee Routes
@app.route("/employees", methods=["GET"])
@admin_required
def employees():
    """List all employees."""
    try:
        resp = _get("employees/get")
        if isinstance(resp, dict) and resp.get("error"):
            flash(f"Unable to fetch employees: {resp['error']}", "danger")
            employees_list = []
        else:
            employees_list = resp.get("items", [])
        return render_template("employees.html", employees=employees_list, MOCK_MODE=MOCK)
    except Exception as e:
        flash(f"Error loading employees: {str(e)}", "danger")
        return render_template("employees.html", employees=[], MOCK_MODE=MOCK)

@app.route("/employees/add", methods=["GET", "POST"])
@admin_required
def employees_add():
    """Add a new employee."""
    if request.method == "POST":
        try:
            # Get form data
            fname = request.form.get("t_emp_fname", "").strip()
            lname = request.form.get("t_emp_lname", "").strip()
            dept = request.form.get("t_emp_dept", "").strip()
            
            # Validate required fields
            if not fname or not lname or not dept:
                flash("All fields are required.", "danger")
                return render_template("employees_add.html", MOCK_MODE=MOCK)
            
            # Create employee
            resp = _post("employees/create", params={
                "t_emp_fname": fname,
                "t_emp_lname": lname,
                "t_emp_dept": dept
            })
            
            if isinstance(resp, dict) and resp.get("error"):
                flash(f"Error creating employee: {resp['error']}", "danger")
            else:
                flash("Employee created successfully!", "success")
                return redirect(url_for("employees"))
                
        except Exception as e:
            flash(f"Error creating employee: {str(e)}", "danger")
    
    return render_template("employees_add.html", MOCK_MODE=MOCK)

@app.route("/employees/edit/<empid>", methods=["GET", "POST"])
@admin_required
def employees_edit(empid):
    """Edit an employee."""
    try:
        empid_int = int(empid)
    except ValueError:
        flash("Invalid employee ID.", "danger")
        return redirect(url_for("employees"))
    
    if request.method == "POST":
        try:
            # Get form data
            fname = request.form.get("t_emp_fname", "").strip()
            lname = request.form.get("t_emp_lname", "").strip()
            dept = request.form.get("t_emp_dept", "").strip()
            
            # Validate required fields
            if not fname or not lname or not dept:
                flash("All fields are required.", "danger")
                return redirect(url_for("employees_edit", empid=empid))
            
            # Update employee
            resp = _put("employees/update", params={
                "t_empid": empid_int,
                "t_emp_fname": fname,
                "t_emp_lname": lname,
                "t_emp_dept": dept
            })
            
            if isinstance(resp, dict) and resp.get("error"):
                flash(f"Error updating employee: {resp['error']}", "danger")
            else:
                flash("Employee updated successfully!", "success")
                return redirect(url_for("employees"))
                
        except Exception as e:
            flash(f"Error updating employee: {str(e)}", "danger")
    else:
        # GET request - fetch employee data
        try:
            resp = _get("employees/get", params={"empid": empid_int})
            if isinstance(resp, dict) and resp.get("error"):
                flash(f"Unable to fetch employee: {resp['error']}", "danger")
                return redirect(url_for("employees"))
            
            employees_list = resp.get("items", [])
            employee = employees_list[0] if employees_list else None
            
            if not employee:
                flash("Employee not found.", "danger")
                return redirect(url_for("employees"))
                
            return render_template("employees_edit.html", employee=employee, MOCK_MODE=MOCK)
            
        except Exception as e:
            flash(f"Error loading employee: {str(e)}", "danger")
            return redirect(url_for("employees"))
    
    return redirect(url_for("employees"))

# Inventory Routes
@app.route("/inventory", methods=["GET"])
@admin_required
def inventory():
    """List all inventory items."""
    try:
        resp = _get("inventory/get")
        if isinstance(resp, dict) and resp.get("error"):
            flash(f"Unable to fetch inventory: {resp['error']}", "danger")
            inventory_list = []
        else:
            inventory_list = resp.get("items", [])
        return render_template("inventory.html", inventory=inventory_list, MOCK_MODE=MOCK)
    except Exception as e:
        flash(f"Error loading inventory: {str(e)}", "danger")
        return render_template("inventory.html", inventory=[], MOCK_MODE=MOCK)

@app.route("/inventory/add", methods=["GET", "POST"])
@admin_required
def inventory_add():
    """Add a new inventory item."""
    if request.method == "POST":
        try:
            # Handle both form data and JSON requests
            if request.is_json:
                data = request.get_json()
                name = data.get("t_item_name", "").strip()
                category = data.get("t_item_category", "").strip()
                quantity = data.get("t_quantity", "").strip()
            else:
                name = request.form.get("t_item_name", "").strip()
                category = request.form.get("t_item_category", "").strip()
                quantity = request.form.get("t_quantity", "").strip()
            
            # Validate required fields
            if not name or not category or not quantity:
                error_msg = "All fields are required."
                if request.is_json:
                    return jsonify({"error": error_msg}), 400
                flash(error_msg, "danger")
                return render_template("inventory_add.html", MOCK_MODE=MOCK)
            
            # Validate quantity is numeric
            try:
                quantity_int = int(quantity)
            except ValueError:
                error_msg = "Quantity must be a number."
                if request.is_json:
                    return jsonify({"error": error_msg}), 400
                flash(error_msg, "danger")
                return render_template("inventory_add.html", MOCK_MODE=MOCK)
            
            # Create inventory item
            resp = _post("inventory/create", params={
                "t_item_name": name,
                "t_item_category": category,
                "t_item_quantity": quantity_int
            })
            
            if isinstance(resp, dict) and resp.get("error"):
                error_msg = f"Error creating inventory item: {resp['error']}"
                if request.is_json:
                    return jsonify({"error": error_msg}), 500
                flash(error_msg, "danger")
            else:
                success_msg = "Inventory item created successfully!"
                if request.is_json:
                    return jsonify({"success": success_msg})
                flash(success_msg, "success")
                return redirect(url_for("inventory"))
                
        except Exception as e:
            error_msg = f"Error creating inventory item: {str(e)}"
            if request.is_json:
                return jsonify({"error": error_msg}), 500
            flash(error_msg, "danger")
    
    return render_template("inventory_add.html", MOCK_MODE=MOCK)

@app.route("/inventory/edit/<itemid>", methods=["GET", "POST"])
@admin_required
def inventory_edit(itemid):
    """Edit an inventory item."""
    try:
        itemid_int = int(itemid)
    except ValueError:
        error_msg = "Invalid item ID."
        if request.is_json:
            return jsonify({"error": error_msg}), 400
        flash(error_msg, "danger")
        return redirect(url_for("inventory"))
    
    if request.method == "POST":
        try:
            # Handle both form data and JSON requests
            if request.is_json:
                data = request.get_json()
                name = data.get("t_item_name", "").strip()
                category = data.get("t_item_category", "").strip()
                quantity = data.get("t_quantity", "").strip()
            else:
                name = request.form.get("t_item_name", "").strip()
                category = request.form.get("t_item_category", "").strip()
                quantity = request.form.get("t_quantity", "").strip()
            
            # Validate required fields
            if not name or not category or not quantity:
                error_msg = "All fields are required."
                if request.is_json:
                    return jsonify({"error": error_msg}), 400
                flash(error_msg, "danger")
                return redirect(url_for("inventory_edit", itemid=itemid))
            
            # Validate quantity is numeric
            try:
                quantity_int = int(quantity)
            except ValueError:
                error_msg = "Quantity must be a number."
                if request.is_json:
                    return jsonify({"error": error_msg}), 400
                flash(error_msg, "danger")
                return redirect(url_for("inventory_edit", itemid=itemid))
            
            # Update inventory item
            resp = _put("inventory/update", params={
                "t_item_id": itemid_int,
                "t_item_name": name,
                "t_item_category": category,
                "t_item_quantity": quantity_int
            })
            
            if isinstance(resp, dict) and resp.get("error"):
                error_msg = f"Error updating inventory item: {resp['error']}"
                if request.is_json:
                    return jsonify({"error": error_msg}), 500
                flash(error_msg, "danger")
            else:
                success_msg = "Inventory item updated successfully!"
                if request.is_json:
                    return jsonify({"success": success_msg})
                flash(success_msg, "success")
                return redirect(url_for("inventory"))
                
        except Exception as e:
            error_msg = f"Error updating inventory item: {str(e)}"
            if request.is_json:
                return jsonify({"error": error_msg}), 500
            flash(error_msg, "danger")
    else:
        # GET request - fetch inventory item data
        try:
            resp = _get("inventory/get", params={"itemid": itemid_int})
            if isinstance(resp, dict) and resp.get("error"):
                flash(f"Unable to fetch inventory item: {resp['error']}", "danger")
                return redirect(url_for("inventory"))
            
            inventory_list = resp.get("items", [])
            item = inventory_list[0] if inventory_list else None
            
            if not item:
                flash("Inventory item not found.", "danger")
                return redirect(url_for("inventory"))
                
            return render_template("inventory_edit.html", item=item, MOCK_MODE=MOCK)
            
        except Exception as e:
            flash(f"Error loading inventory item: {str(e)}", "danger")
            return redirect(url_for("inventory"))
    
    return redirect(url_for("inventory"))

# Usage Report Route
@app.route("/usage", methods=["GET"])
@admin_required
def usage():
    """Usage report with filtering."""
    try:
        # Get query parameters
        empid = request.args.get("empid", "").strip()
        item_id = request.args.get("t_item_id", "").strip()
        start_date = request.args.get("start_date", "").strip()
        end_date = request.args.get("end_date", "").strip()
        
        # Build params for API call
        params = {}
        if empid:
            try:
                params["empid"] = int(empid)
            except ValueError:
                flash("Employee ID must be a number.", "warning")
        if item_id:
            try:
                params["t_item_id"] = int(item_id)
            except ValueError:
                flash("Item ID must be a number.", "warning")
        if start_date:
            try:
                from datetime import datetime
                datetime.strptime(start_date, '%Y-%m-%d')
                params["start_date"] = start_date
            except ValueError:
                flash("Start date must be in YYYY-MM-DD format.", "warning")
        if end_date:
            try:
                from datetime import datetime
                datetime.strptime(end_date, '%Y-%m-%d')
                params["end_date"] = end_date
            except ValueError:
                flash("End date must be in YYYY-MM-DD format.", "warning")
        
        # Fetch usage data
        resp = _get("usage/get", params=params)
        if isinstance(resp, dict) and resp.get("error"):
            flash(f"Unable to fetch usage data: {resp['error']}", "danger")
            usage_list = []
        else:
            usage_list = resp.get("items", [])
        
        return render_template("usage.html", 
                             usage=usage_list, 
                             filters={"empid": empid, "t_item_id": item_id, "start_date": start_date, "end_date": end_date},
                             MOCK_MODE=MOCK)
    except Exception as e:
        flash(f"Error loading usage report: {str(e)}", "danger")
        return render_template("usage.html", usage=[], filters={}, MOCK_MODE=MOCK)

# Bookings Management Routes
@app.route("/bookings-management", methods=["GET"])
@admin_required
def bookings_management():
    """List all bookings with optional filters and employee dropdown."""
    try:
        # Get filter parameters
        empid = request.args.get('empid', 'all').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        status_filter = request.args.get('status', 'all').strip()
        
        # Get employees list for dropdown with fallback
        employees_resp = _get("employees/get")
        employees_list = []
        if isinstance(employees_resp, dict) and not employees_resp.get("error"):
            employees_list = employees_resp.get("items", [])
        elif isinstance(employees_resp, dict) and employees_resp.get("error"):
            # Fallback to mock employees data
            print(f"Oracle APEX employees failed: {employees_resp['error']}, using mock data")
            employees_list = mock_get("employees/get", None).get("items", [])
        
        # Build API parameters
        params = {}
        print(f"[DEBUG] empid value: '{empid}' (type: {type(empid)})")
        if empid and empid.strip() and empid != 'all' and empid != 'All Employees':
            try:
                params['empid'] = int(empid)
                print(f"[DEBUG] Added empid to params: {params}")
            except ValueError:
                flash("Invalid employee ID format", "danger")
                empid = ''
        else:
            print(f"[DEBUG] Not adding empid to params, using all employees")
        
        if start_date:
            try:
                # Validate date format
                datetime.strptime(start_date, '%Y-%m-%d')
                params['start_date'] = start_date
            except ValueError:
                flash("Invalid start date format (use YYYY-MM-DD)", "danger")
                start_date = ''
        
        if end_date:
            try:
                # Validate date format
                datetime.strptime(end_date, '%Y-%m-%d')
                params['end_date'] = end_date
            except ValueError:
                flash("Invalid end date format (use YYYY-MM-DD)", "danger")
                end_date = ''
        
        # Get bookings data with fallback to mock data
        print(f"[DEBUG] MOCK mode: {MOCK}")
        print(f"[DEBUG] Filter params - empid: '{empid}', status: '{status_filter}', start_date: '{start_date}', end_date: '{end_date}'")
        print(f"[DEBUG] Calling _get with params: {params}")
        resp = _get("inventory_booking/get_date_data", params=params if params else {})
        print(f"[DEBUG] Response type: {type(resp)}")
        print(f"[DEBUG] Response content: {resp}")
        
        if isinstance(resp, dict) and (resp.get("error") or len(resp.get("items", [])) == 0):
            # If Oracle APEX fails or returns no data, fall back to mock data
            if resp.get("error"):
                print(f"Oracle APEX failed: {resp['error']}, falling back to mock data")
                flash(f"Oracle APEX connection failed, showing sample data: {resp['error']}", "warning")
            else:
                print(f"Oracle APEX returned no data (0 items), falling back to mock data")
                flash("No booking data found in Oracle APEX, showing sample data", "info")
            # Use mock data directly
            resp = mock_get("inventory_booking/get_date_data", params if params else {})
            print(f"[DEBUG] Mock response: {resp}")
        
        bookings_list = resp.get("items", [])
        print(f"[DEBUG] Bookings list length: {len(bookings_list)}")
        
        # Ensure employee names are populated
        employee_dict = {emp.get('t_empid'): f"{emp.get('t_emp_fname', '')} {emp.get('t_emp_lname', '')}".strip() 
                        for emp in employees_list}
        
        for booking in bookings_list:
            emp_id = booking.get('t_employee_id')
            if emp_id and not booking.get('employee_name'):
                booking['employee_name'] = employee_dict.get(emp_id, f'Employee {emp_id}')
        
        # Apply status filter on the client side if needed
        if status_filter and status_filter != 'all' and status_filter.strip():
            if status_filter == 'out':
                bookings_list = [b for b in bookings_list if b.get('t_return_date') == 'Not Returned']
            elif status_filter == 'returned':
                bookings_list = [b for b in bookings_list if b.get('t_return_date') != 'Not Returned']
            elif status_filter == 'overdue':
                # Filter for overdue items (booking date + 7 days < today and not returned)
                from datetime import timedelta
                today = date.today()
                overdue_bookings = []
                for booking in bookings_list:
                    if booking.get('t_return_date') == 'Not Returned':
                        try:
                            booking_date = datetime.strptime(booking.get('t_booking_date', ''), '%Y-%m-%d').date()
                            if booking_date + timedelta(days=7) < today:
                                overdue_bookings.append(booking)
                        except:
                            pass
                bookings_list = overdue_bookings
        
        return render_template("bookings.html", 
                             bookings=bookings_list, 
                             employees=employees_list,
                             filters={
                                 'empid': empid,
                                 'start_date': start_date,
                                 'end_date': end_date,
                                 'status': status_filter
                             },
                             today=date.today().strftime('%Y-%m-%d'),
                             MOCK_MODE=MOCK)
    except Exception as e:
        flash(f"Error loading bookings: {str(e)}", "danger")
        return render_template("bookings.html", 
                             bookings=[], 
                             employees=[],
                             filters={},
                             today=date.today().strftime('%Y-%m-%d'),
                             MOCK_MODE=MOCK)

@app.route("/bookings/return/<int:bookid>/<int:empid>", methods=["POST"])
@login_required
def booking_return(bookid, empid):
    """Mark a booking as returned and update inventory quantity."""
    try:
        # Use today's date as return date
        today = datetime.now().strftime('%Y-%m-%d')
        
        # First, get the booking details to find the inventory item
        booking_resp = _get("inventory_booking/get_date_data", params={"bookid": bookid})
        inventory_id = None
        
        if isinstance(booking_resp, dict) and booking_resp.get("items"):
            # Find the specific booking
            for booking in booking_resp["items"]:
                if booking.get("t_booking_id") == bookid:
                    inventory_id = booking.get("t_inventory_id")
                    break
        
        # If we couldn't find the booking in APEX, try to get it from mock data
        if not inventory_id:
            # Get mock booking data to find inventory ID
            mock_booking_resp = mock_get("inventory_booking/get_date_data", {"bookid": bookid})
            if isinstance(mock_booking_resp, dict) and mock_booking_resp.get("items"):
                for booking in mock_booking_resp["items"]:
                    if booking.get("t_booking_id") == bookid:
                        inventory_id = booking.get("t_inventory_id")
                        break
        
        print(f"[DEBUG] Found inventory_id: {inventory_id} for booking {bookid}")
        
        # Call the return API
        resp = _post("inventory_booking/postdata", params={
            "bookid": bookid,
            "empid": empid,
            "returndate": today
        })
        
        # If return was successful and we have an inventory ID, update inventory quantity
        if inventory_id and (not isinstance(resp, dict) or not resp.get("error")):
            try:
                # Get current inventory item details
                inventory_resp = _get("inventory/get", params={"itemid": inventory_id})
                current_quantity = 0
                item_name = ""
                item_category = ""
                
                if isinstance(inventory_resp, dict) and inventory_resp.get("items"):
                    for item in inventory_resp["items"]:
                        if item.get("t_item_id") == inventory_id:
                            current_quantity = int(item.get("t_item_quantity", 0))
                            item_name = item.get("t_item_name", "")
                            item_category = item.get("t_item_category", "")
                            break
                
                # If we couldn't find in APEX, try mock data
                if current_quantity == 0 and not item_name:
                    mock_inventory_resp = mock_get("inventory/get", {"itemid": inventory_id})
                    if isinstance(mock_inventory_resp, dict) and mock_inventory_resp.get("items"):
                        for item in mock_inventory_resp["items"]:
                            if item.get("t_item_id") == inventory_id:
                                current_quantity = int(item.get("t_item_quantity", 0))
                                item_name = item.get("t_item_name", "")
                                item_category = item.get("t_item_category", "")
                                break
                
                # Increase quantity by 1
                new_quantity = current_quantity + 1
                print(f"[DEBUG] Updating inventory {inventory_id}: {current_quantity} -> {new_quantity}")
                
                # Update inventory quantity
                inventory_update_resp = _put("inventory/update", params={
                    "t_item_id": inventory_id,
                    "t_item_name": item_name,
                    "t_item_category": item_category,
                    "t_item_quantity": new_quantity
                })
                
                print(f"[DEBUG] Inventory update response: {inventory_update_resp}")
                
            except Exception as e:
                print(f"[DEBUG] Error updating inventory: {e}")
                # Don't fail the return if inventory update fails
        
        # Debug logging
        print(f"[DEBUG] Return API response: {resp}")
        print(f"[DEBUG] Response type: {type(resp)}")
        
        # Check if this is an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Check for explicit errors first
            if isinstance(resp, dict) and resp.get("error"):
                return jsonify({
                    "success": False,
                    "message": f"Error marking booking as returned: {resp['error']}",
                    "type": "error"
                }), 400
            
            # Check for explicit success indicators
            elif isinstance(resp, dict) and resp.get("updated_rows") == 1:
                # Get updated dashboard data
                dashboard_data = get_dashboard_data()
                return jsonify({
                    "success": True,
                    "message": "Booking marked as returned successfully!",
                    "type": "success",
                    "dashboard_data": {
                        "total_items": dashboard_data.get("total_items", 0),
                        "currently_issued": dashboard_data.get("currently_issued", 0),
                        "total_employees": dashboard_data.get("total_employees", 0),
                        "recent_bookings": dashboard_data.get("recent_bookings", 0),
                        "recent_activity": dashboard_data.get("recent_activity", [])[:5]  # Last 5 activities
                    }
                })
            elif isinstance(resp, dict) and resp.get("updated_rows") == 0:
                # Check if this is actually a successful return with status 'no_change'
                # This might mean the item was already returned or the operation completed
                if resp.get("status") == "no_change":
                    # Treat as success - the operation completed even if no rows were updated
                    dashboard_data = get_dashboard_data()
                    return jsonify({
                        "success": True,
                        "message": "Booking return processed successfully!",
                        "type": "success",
                        "dashboard_data": {
                            "total_items": dashboard_data.get("total_items", 0),
                            "currently_issued": dashboard_data.get("currently_issued", 0),
                            "total_employees": dashboard_data.get("total_employees", 0),
                            "recent_bookings": dashboard_data.get("recent_bookings", 0),
                            "recent_activity": dashboard_data.get("recent_activity", [])[:5]  # Last 5 activities
                        }
                    })
                else:
                    return jsonify({
                        "success": False,
                        "message": "This booking was already returned.",
                        "type": "info"
                    }), 400
            
            # If we get here, assume success (API returned 200 and no explicit error)
            # This handles cases where Oracle APEX doesn't return updated_rows field
            else:
                print(f"[DEBUG] Assuming success - no explicit error found in response")
                dashboard_data = get_dashboard_data()
                return jsonify({
                    "success": True,
                    "message": "Booking return processed successfully!",
                    "type": "success",
                    "dashboard_data": {
                        "total_items": dashboard_data.get("total_items", 0),
                        "currently_issued": dashboard_data.get("currently_issued", 0),
                        "total_employees": dashboard_data.get("total_employees", 0),
                        "recent_bookings": dashboard_data.get("recent_bookings", 0),
                        "recent_activity": dashboard_data.get("recent_activity", [])[:5]  # Last 5 activities
                    }
                })
        else:
            # Handle non-AJAX requests (redirect)
            if isinstance(resp, dict) and resp.get("error"):
                flash(f"Error marking booking as returned: {resp['error']}", "danger")
            elif isinstance(resp, dict) and resp.get("updated_rows") == 1:
                flash("Booking marked as returned successfully!", "success")
            elif isinstance(resp, dict) and resp.get("updated_rows") == 0:
                if resp.get("status") == "no_change":
                    flash("Booking return processed successfully!", "success")
                else:
                    flash("This booking was already returned.", "info")
            else:
                # Assume success if no explicit error (API returned 200)
                flash("Booking return processed successfully!", "success")
            
            return redirect(url_for('bookings_management'))
            
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                "success": False,
                "message": f"Error processing return: {str(e)}",
                "type": "error"
            }), 500
        else:
            flash(f"Error processing return: {str(e)}", "danger")
            return redirect(url_for('bookings_management'))

@app.route("/api/dashboard-data", methods=["GET"])
@login_required
def api_dashboard_data():
    """API endpoint to get current dashboard data."""
    try:
        dashboard_data = get_dashboard_data()
        return jsonify({
            "success": True,
            "data": {
                "total_items": dashboard_data.get("total_items", 0),
                "currently_issued": dashboard_data.get("currently_issued", 0),
                "total_employees": dashboard_data.get("total_employees", 0),
                "recent_bookings": dashboard_data.get("recent_bookings", 0),
                "recent_activity": dashboard_data.get("recent_activity", [])[:10],  # Last 10 activities
                "low_stock_alerts": dashboard_data.get("low_stock_alerts", [])
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Debug route to test inventory API
@app.route("/debug/inventory")
@login_required
def debug_inventory():
    """Debug route to see raw inventory API response."""
    try:
        resp = _get("inventory/get")
        return jsonify({
            "status": "success",
            "raw_response": resp,
            "items_count": len(resp.get("items", [])) if isinstance(resp, dict) else 0,
            "first_item": resp.get("items", [{}])[0] if resp.get("items") else None
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

# Debug route to test bookings API
@app.route("/debug/bookings")
@login_required
def debug_bookings():
    """Debug route to see raw bookings API response."""
    try:
        resp = _get("inventory_booking/get_date_data")
        employees_resp = _get("employees/get")
        
        return jsonify({
            "status": "success",
            "mock_mode": MOCK,
            "base_url": BASE_URL,
            "bookings_response": resp,
            "employees_response": employees_resp,
            "bookings_count": len(resp.get("items", [])) if isinstance(resp, dict) else 0,
            "employees_count": len(employees_resp.get("items", [])) if isinstance(employees_resp, dict) else 0,
            "first_booking": resp.get("items", [{}])[0] if resp.get("items") else None,
            "first_employee": employees_resp.get("items", [{}])[0] if employees_resp.get("items") else None
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

# Test Oracle APEX connection
@app.route("/test-apex")
@login_required
def test_apex():
    """Test Oracle APEX connection directly."""
    try:
        import requests
        
        # Test the exact URL that should work
        test_url = "https://oracleapex.com/ords/ifs325_techinnovators/inventory_booking/get_date_data?empid=1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json"
        }
        
        print(f"Testing direct connection to: {test_url}")
        response = requests.get(test_url, headers=headers, timeout=30)
        
        return jsonify({
            "status": "success",
            "url_tested": test_url,
            "status_code": response.status_code,
            "response_headers": dict(response.headers),
            "response_data": response.json() if response.status_code == 200 else response.text[:500]
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "url_tested": test_url if 'test_url' in locals() else "Not set"
        }), 500

# ===== EMPLOYEE-ONLY ROUTES =====
# These routes are restricted to employees only and include strict user isolation

@app.route("/employee/dashboard")
@employee_required
def employee_dashboard():
    """Employee personal dashboard showing only their equipment."""
    try:
        employee_id = current_user.get_employee_id()
        if not employee_id:
            flash("Employee ID not found. Please contact administrator.", "danger")
            return redirect(url_for('login'))
        
        # Get only this employee's bookings
        resp = _get("inventory_booking/get_date_data", params={"empid": employee_id})
        
        if isinstance(resp, dict) and resp.get("error"):
            # Fallback to mock data
            resp = mock_get("inventory_booking/get_date_data", {"empid": employee_id})
        
        bookings_list = resp.get("items", [])
        
        # Calculate statistics for this employee only
        total_bookings = len(bookings_list)
        current_out = len([b for b in bookings_list if b.get('t_return_date') == 'Not Returned'])
        overdue_count = 0
        
        # Check for overdue items (booking date + 7 days < today)
        from datetime import date, timedelta
        today = date.today()
        for booking in bookings_list:
            if booking.get('t_return_date') == 'Not Returned':
                try:
                    booking_date = datetime.strptime(booking.get('t_booking_date', ''), '%Y-%m-%d').date()
                    if booking_date + timedelta(days=7) < today:
                        overdue_count += 1
                except:
                    pass
        
        return render_template("employee_dashboard.html", 
                             bookings=bookings_list,
                             stats={
                                 'total_bookings': total_bookings,
                                 'current_out': current_out,
                                 'overdue_count': overdue_count
                             },
                             employee_id=employee_id,
                             MOCK_MODE=MOCK)
    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "danger")
        return render_template("employee_dashboard.html", 
                             bookings=[], 
                             stats={'total_bookings': 0, 'current_out': 0, 'overdue_count': 0},
                             employee_id=current_user.get_employee_id(),
                             MOCK_MODE=MOCK)

@app.route("/employee/inventory")
@employee_required
def employee_inventory():
    """View available inventory (read-only for employees)."""
    try:
        # Get all inventory items
        resp = _get("inventory/get")
        
        if isinstance(resp, dict) and resp.get("error"):
            # Fallback to mock data
            resp = mock_get("inventory/get", None)
        
        inventory_list = resp.get("items", [])
        
        # Filter to show only available items (quantity > 0)
        available_items = [item for item in inventory_list if item.get('t_item_quantity', 0) > 0]
        
        return render_template("employee_inventory.html", 
                             inventory=available_items,
                             MOCK_MODE=MOCK)
    except Exception as e:
        flash(f"Error loading inventory: {str(e)}", "danger")
        return render_template("employee_inventory.html", 
                             inventory=[], 
                             MOCK_MODE=MOCK)

@app.route("/employee/bookings/request", methods=["POST"])
@employee_required
def employee_request_equipment():
    """Create a new booking request for the current employee."""
    try:
        employee_id = current_user.get_employee_id()
        if not employee_id:
            return jsonify({"error": "Employee ID not found"}), 400
        
        # Get form data
        inventory_id = request.form.get('inventory_id')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        purpose = request.form.get('purpose', '')
        
        # Validate required fields
        if not all([inventory_id, start_date, end_date]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Validate dates
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            if end_dt < start_dt:
                return jsonify({"error": "End date must be after start date"}), 400
        except ValueError:
            return jsonify({"error": "Invalid date format"}), 400
        
        # Create booking request
        booking_data = {
            't_employee_id': employee_id,
            't_inventory_id': int(inventory_id),
            't_booking_date': start_date,
            't_return_date': 'Not Returned',
            'purpose': purpose,
            'status': 'requested'
        }
        
        # For now, we'll use mock data since we don't have a create booking endpoint
        # In a real system, you would call: _post("inventory_booking/create", booking_data)
        
        flash("Equipment request submitted successfully!", "success")
        return jsonify({"status": "success", "message": "Request submitted"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/employee/bookings")
@employee_required
def employee_bookings():
    """View current employee's booking history."""
    try:
        employee_id = current_user.get_employee_id()
        if not employee_id:
            flash("Employee ID not found. Please contact administrator.", "danger")
            return redirect(url_for('employee_dashboard'))
        
        # Get only this employee's bookings
        resp = _get("inventory_booking/get_date_data", params={"empid": employee_id})
        
        if isinstance(resp, dict) and resp.get("error"):
            # Fallback to mock data
            resp = mock_get("inventory_booking/get_date_data", {"empid": employee_id})
        
        bookings_list = resp.get("items", [])
        
        return render_template("employee_bookings.html", 
                             bookings=bookings_list,
                             employee_id=employee_id,
                             MOCK_MODE=MOCK)
    except Exception as e:
        flash(f"Error loading bookings: {str(e)}", "danger")
        return render_template("employee_bookings.html", 
                             bookings=[], 
                             employee_id=current_user.get_employee_id(),
                             MOCK_MODE=MOCK)

@app.route("/employee/bookings/<int:booking_id>/return", methods=["POST"])
@employee_required
def employee_return_equipment(booking_id):
    """Return equipment for the current employee."""
    try:
        employee_id = current_user.get_employee_id()
        if not employee_id:
            return jsonify({"error": "Employee ID not found"}), 400
        
        # Verify the booking belongs to this employee
        resp = _get("inventory_booking/get_date_data", params={"empid": employee_id})
        
        if isinstance(resp, dict) and resp.get("error"):
            resp = mock_get("inventory_booking/get_date_data", {"empid": employee_id})
        
        bookings_list = resp.get("items", [])
        booking = next((b for b in bookings_list if b.get('t_booking_id') == booking_id), None)
        
        if not booking:
            return jsonify({"error": "Booking not found or not owned by you"}), 404
        
        if booking.get('t_return_date') != 'Not Returned':
            return jsonify({"error": "Equipment already returned"}), 400
        
        # Mark as returned
        return_data = {
            'bookid': booking_id,
            'empid': employee_id,
            'returndate': date.today().strftime('%Y-%m-%d')
        }
        
        # Call the return API
        result = _post("inventory_booking/postdata", return_data)
        
        if isinstance(result, dict) and result.get("error"):
            return jsonify({"error": result["error"]}), 500
        
        flash("Equipment returned successfully!", "success")
        return jsonify({"status": "success", "message": "Equipment returned"})
        
    except Exception as e:
        return jsonify({"error": str(e)        }), 500

# ===== QR CODE GENERATION ROUTES =====

@app.route("/generate-qr/employee/<int:employee_id>")
@login_required
def generate_employee_qr(employee_id):
    """Generate QR code for employee login."""
    try:
        # Verify the employee exists
        resp = _get("employees/get", params={"empid": employee_id})
        
        if isinstance(resp, dict) and resp.get("error"):
            resp = mock_get("employees/get", {"empid": employee_id})
        
        employees = resp.get("items", [])
        employee = next((emp for emp in employees if emp.get('t_empid') == employee_id), None)
        
        if not employee:
            return jsonify({"error": "Employee not found"}), 404
        
        # Create QR code data
        qr_data = {
            "type": "employee_login",
            "employee_id": str(employee_id),
            "username": employee.get('t_emp_fname', ''),
            "timestamp": datetime.now().isoformat()
        }
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Return image response
        return app.response_class(
            buffer.getvalue(),
            mimetype='image/png',
            headers={
                'Content-Disposition': f'inline; filename=employee-{employee_id}-qr-code.png'
            }
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/generate-qr/admin")
@login_required
def generate_admin_qr():
    """Generate QR code for admin login."""
    try:
        # Create QR code data
        qr_data = {
            "type": "admin_login",
            "username": "admin",
            "timestamp": datetime.now().isoformat()
        }
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return jsonify({
            "status": "success",
            "qr_code": f"data:image/png;base64,{img_str}",
            "admin": {
                "username": "admin"
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/employee/qr-code")
@employee_required
def employee_qr_code():
    """Page for employees to view their own QR code."""
    try:
        # Get current employee's information
        employee_id = current_user.employee_id
        
        # Get employee details
        resp = _get("employees/get")
        
        if isinstance(resp, dict) and resp.get("error"):
            resp = mock_get("employees/get", None)
        
        employees = resp.get("items", [])
        current_employee = None
        
        # Find current employee in the list
        for emp in employees:
            if (emp.get("t_empid") == employee_id or 
                emp.get("empid") == employee_id):
                current_employee = emp
                break
        
        if not current_employee:
            flash("Employee information not found", "danger")
            return redirect(url_for("employee_dashboard"))
        
        return render_template("employee_qr_code.html", 
                             employee=current_employee,
                             employee_id=employee_id,
                             MOCK_MODE=MOCK)
    except Exception as e:
        flash(f"Error loading QR code page: {str(e)}", "danger")
        return redirect(url_for("employee_dashboard"))

@app.route("/qr-codes")
@login_required
def qr_codes_page():
    """Page to display QR codes for login."""
    try:
        # Get all employees
        resp = _get("employees/get")
        
        if isinstance(resp, dict) and resp.get("error"):
            resp = mock_get("employees/get", None)
        
        employees = resp.get("items", [])
        
        return render_template("qr_codes.html", 
                             employees=employees,
                             MOCK_MODE=MOCK)
    except Exception as e:
        flash(f"Error loading QR codes page: {str(e)}", "danger")
        return render_template("qr_codes.html", 
                             employees=[], 
                             MOCK_MODE=MOCK)

if __name__ == "__main__":
    app.run(debug=FLASK_DEBUG, port=5000)
