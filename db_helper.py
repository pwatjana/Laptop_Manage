import os
import sqlite3
from dotenv import load_dotenv
from supabase import create_client, Client
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "laptop_db.db")

use_supabase = False
supabase_client = None

# Check Supabase connection
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        # Try a quick query to test connection (using Laptop_SN_no instead of SerialNumber)
        supabase_client.table("laptops").select("Laptop_SN_no").limit(1).execute()
        use_supabase = True
        print("Connected to Supabase. Online database active.")
    except Exception as e:
        print(f"Supabase connection test failed: {e}. Falling back to SQLite.")
        use_supabase = False
else:
    print("Supabase credentials invalid or missing. Using SQLite.")
    use_supabase = False

def get_sqlite_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize SQLite tables to match the new Supabase schema."""
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    
    # 1. Users table (for admin auth)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        Username TEXT PRIMARY KEY,
        PasswordHash TEXT NOT NULL,
        Role TEXT NOT NULL
    )
    """)
    
    # 2. Laptops table (aligned with laptop.csv)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS laptops (
        Laptop_SN_no TEXT PRIMARY KEY,
        No INTEGER,
        Asset_number TEXT,
        RFID TEXT,
        Laptop_Brand TEXT NOT NULL,
        Date_of_Purchase TEXT,
        Date_end_of_life TEXT,
        Warranty_type TEXT,
        Warranty_period TEXT,
        Status TEXT DEFAULT 'Available'
    )
    """)
    
    # 3. Employees table (aligned with employee.csv)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        Employee_code TEXT PRIMARY KEY,
        Employee_full_name TEXT NOT NULL,
        Section TEXT,
        Join_date TEXT,
        Resign_Date TEXT
    )
    """)
    
    # 4. Allocations table (Onboarding / Offboarding)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS allocations (
        AllocationId INTEGER PRIMARY KEY AUTOINCREMENT,
        SerialNumber TEXT NOT NULL,
        EmployeeCode TEXT NOT NULL,
        AllocationType TEXT NOT NULL, -- 'Onboarding', 'Offboarding'
        HandoverDate TEXT NOT NULL,
        ReturnDate TEXT,
        HandoverBy TEXT NOT NULL,
        ReceivedBy TEXT NOT NULL,
        Condition TEXT,
        Status TEXT DEFAULT 'Active', -- 'Active', 'Returned'
        FOREIGN KEY (SerialNumber) REFERENCES laptops (Laptop_SN_no) ON DELETE CASCADE,
        FOREIGN KEY (EmployeeCode) REFERENCES employees (Employee_code) ON DELETE CASCADE
    )
    """)
    
    # 5. Damage Issues table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS damage_issues (
        IssueId INTEGER PRIMARY KEY AUTOINCREMENT,
        SerialNumber TEXT NOT NULL,
        EmployeeCode TEXT,
        ReportedDate TEXT NOT NULL,
        Description TEXT NOT NULL,
        Severity TEXT NOT NULL, -- 'Low', 'Medium', 'High', 'Critical'
        Status TEXT DEFAULT 'Open', -- 'Open', 'In Repair', 'Resolved', 'Scrapped'
        ActionTaken TEXT,
        ResolutionDate TEXT,
        Cost REAL DEFAULT 0.0,
        FOREIGN KEY (SerialNumber) REFERENCES laptops (Laptop_SN_no) ON DELETE CASCADE,
        FOREIGN KEY (EmployeeCode) REFERENCES employees (Employee_code) ON DELETE SET NULL
    )
    """)
    
    conn.commit()
    
    # Seed default Admin User if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        admin_pass_hash = generate_password_hash("admin123")
        cursor.execute("INSERT INTO users VALUES (?, ?, ?)", ("admin", admin_pass_hash, "Admin"))
        conn.commit()
        print("Default admin user created: admin / admin123")
        
    conn.close()

# Initialize DB on import
init_db()

# ==================== AUTHENTICATION ====================

def authenticate_admin(username, password):
    if use_supabase:
        try:
            res = supabase_client.table("users").select("*").eq("Username", username).execute()
            if res.data:
                user = res.data[0]
                if check_password_hash(user["PasswordHash"], password):
                    return {"username": user["Username"], "role": user["Role"]}
        except Exception as e:
            print(f"Supabase auth error: {e}")
    
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE Username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row and check_password_hash(row["PasswordHash"], password):
        return {"username": row["Username"], "role": row["Role"]}
    return None

def create_admin_user(username, password, role="Admin"):
    hash_pwd = generate_password_hash(password)
    if use_supabase:
        try:
            supabase_client.table("users").insert({"Username": username, "PasswordHash": hash_pwd, "Role": role}).execute()
            return True
        except Exception as e:
            print(f"Supabase user creation error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users VALUES (?, ?, ?)", (username, hash_pwd, role))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()
    return success

# ==================== DASHBOARD STATS ====================

def get_dashboard_stats():
    stats = {
        "total_laptops": 0,
        "available_laptops": 0,
        "assigned_laptops": 0,
        "repair_laptops": 0,
        "scrapped_laptops": 0,
        "total_employees": 0,
        "active_allocations": 0,
        "open_damages": 0,
        "total_repair_cost": 0.0
    }
    
    if use_supabase:
        try:
            laptops_res = supabase_client.table("laptops").select("Status").execute()
            l_data = laptops_res.data or []
            stats["total_laptops"] = len(l_data)
            stats["available_laptops"] = sum(1 for l in l_data if l.get("Status") == "Available" or l.get("Status") == "Active")
            stats["assigned_laptops"] = sum(1 for l in l_data if l.get("Status") == "Assigned")
            stats["repair_laptops"] = sum(1 for l in l_data if l.get("Status") == "In Repair")
            stats["scrapped_laptops"] = sum(1 for l in l_data if l.get("Status") in ["Scrapped", "EOL"])
            
            employees_res = supabase_client.table("employees").select("Employee_code").execute()
            stats["total_employees"] = len(employees_res.data or [])
            
            alloc_res = supabase_client.table("allocations").select("Status").eq("Status", "Active").execute()
            stats["active_allocations"] = len(alloc_res.data or [])
            
            damage_res = supabase_client.table("damage_issues").select("Status", "Cost").execute()
            d_data = damage_res.data or []
            stats["open_damages"] = sum(1 for d in d_data if d.get("Status") in ["Open", "In Repair"])
            stats["total_repair_cost"] = sum(float(d.get("Cost") or 0.0) for d in d_data)
            return stats
        except Exception as e:
            print(f"Supabase stats query error: {e}. Falling back to SQLite.")

    # SQLite Stats
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*), 
               SUM(CASE WHEN Status='Available' OR Status='Active' THEN 1 ELSE 0 END), 
               SUM(CASE WHEN Status='Assigned' THEN 1 ELSE 0 END), 
               SUM(CASE WHEN Status='In Repair' THEN 1 ELSE 0 END), 
               SUM(CASE WHEN Status='Scrapped' OR Status='EOL' THEN 1 ELSE 0 END) 
        FROM laptops
    """)
    row = cursor.fetchone()
    if row:
        stats["total_laptops"] = row[0] or 0
        stats["available_laptops"] = row[1] or 0
        stats["assigned_laptops"] = row[2] or 0
        stats["repair_laptops"] = row[3] or 0
        stats["scrapped_laptops"] = row[4] or 0
        
    cursor.execute("SELECT COUNT(*) FROM employees")
    stats["total_employees"] = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM allocations WHERE Status='Active'")
    stats["active_allocations"] = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM damage_issues WHERE Status IN ('Open', 'In Repair')")
    stats["open_damages"] = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(Cost) FROM damage_issues")
    stats["total_repair_cost"] = cursor.fetchone()[0] or 0.0
    
    conn.close()
    return stats

# ==================== LAPTOPS CRUD ====================

def get_laptops():
    if use_supabase:
        try:
            res = supabase_client.table("laptops").select("*").order("Laptop_SN_no").execute()
            return res.data
        except Exception as e:
            print(f"Supabase get_laptops error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM laptops ORDER BY Laptop_SN_no")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_laptop(sn):
    if use_supabase:
        try:
            res = supabase_client.table("laptops").select("*").eq("Laptop_SN_no", sn).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"Supabase get_laptop error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM laptops WHERE Laptop_SN_no = ?", (sn,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_laptop(data):
    if use_supabase:
        try:
            supabase_client.table("laptops").insert(data).execute()
            return True
        except Exception as e:
            print(f"Supabase add_laptop error: {e}")
            raise e
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO laptops (Laptop_SN_no, No, Asset_number, RFID, Laptop_Brand, Date_of_Purchase, Date_end_of_life, Warranty_type, Warranty_period, Status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data["Laptop_SN_no"], data.get("No"), data.get("Asset_number"), data.get("RFID"), data["Laptop_Brand"], data.get("Date_of_Purchase"), data.get("Date_end_of_life"), data.get("Warranty_type"), data.get("Warranty_period"), data.get("Status", "Available")))
        conn.commit()
        success = True
    except sqlite3.IntegrityError as e:
        success = False
        raise e
    finally:
        conn.close()
    return success

def update_laptop(sn, data):
    if use_supabase:
        try:
            supabase_client.table("laptops").update(data).eq("Laptop_SN_no", sn).execute()
            return True
        except Exception as e:
            print(f"Supabase update_laptop error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    fields = ", ".join([f"{k} = ?" for k in data.keys()])
    values = list(data.values())
    values.append(sn)
    cursor.execute(f"UPDATE laptops SET {fields} WHERE Laptop_SN_no = ?", values)
    conn.commit()
    conn.close()
    return True

def delete_laptop(sn):
    if use_supabase:
        try:
            supabase_client.table("laptops").delete().eq("Laptop_SN_no", sn).execute()
            return True
        except Exception as e:
            print(f"Supabase delete_laptop error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM laptops WHERE Laptop_SN_no = ?", (sn,))
    conn.commit()
    conn.close()
    return True

# ==================== EMPLOYEES CRUD ====================

def get_employees():
    if use_supabase:
        try:
            res = supabase_client.table("employees").select("*").order("Employee_code").execute()
            return res.data
        except Exception as e:
            print(f"Supabase get_employees error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees ORDER BY Employee_code")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_employee(code):
    if use_supabase:
        try:
            res = supabase_client.table("employees").select("*").eq("Employee_code", code).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"Supabase get_employee error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees WHERE Employee_code = ?", (code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_employee(data):
    if use_supabase:
        try:
            supabase_client.table("employees").insert(data).execute()
            return True
        except Exception as e:
            print(f"Supabase add_employee error: {e}")
            raise e
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO employees (Employee_code, Employee_full_name, Section, Join_date, Resign_Date)
            VALUES (?, ?, ?, ?, ?)
        """, (data["Employee_code"], data["Employee_full_name"], data.get("Section"), data.get("Join_date"), data.get("Resign_Date")))
        conn.commit()
        success = True
    except sqlite3.IntegrityError as e:
        success = False
        raise e
    finally:
        conn.close()
    return success

def update_employee(code, data):
    if use_supabase:
        try:
            supabase_client.table("employees").update(data).eq("Employee_code", code).execute()
            return True
        except Exception as e:
            print(f"Supabase update_employee error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    fields = ", ".join([f"{k} = ?" for k in data.keys()])
    values = list(data.values())
    values.append(code)
    cursor.execute(f"UPDATE employees SET {fields} WHERE Employee_code = ?", values)
    conn.commit()
    conn.close()
    return True

def delete_employee(code):
    if use_supabase:
        try:
            supabase_client.table("employees").delete().eq("Employee_code", code).execute()
            return True
        except Exception as e:
            print(f"Supabase delete_employee error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM employees WHERE Employee_code = ?", (code,))
    conn.commit()
    conn.close()
    return True

# ==================== ALLOCATIONS CRUD (Onboarding/Offboarding) ====================

def get_allocations():
    if use_supabase:
        try:
            res = supabase_client.table("allocations").select("*, laptops(Laptop_Brand), employees(Employee_full_name)").order("AllocationId", desc=True).execute()
            
            flattened = []
            for item in res.data or []:
                flat_item = dict(item)
                laptop_rel = flat_item.pop("laptops", None) or {}
                flat_item["Laptop_Brand"] = laptop_rel.get("Laptop_Brand", "")
                
                emp_rel = flat_item.pop("employees", None) or {}
                flat_item["Employee_full_name"] = emp_rel.get("Employee_full_name", "")
                flattened.append(flat_item)
                
            return flattened
        except Exception as e:
            print(f"Supabase get_allocations error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, l.Laptop_Brand, e.Employee_full_name 
        FROM allocations a
        JOIN laptops l ON a.SerialNumber = l.Laptop_SN_no
        JOIN employees e ON a.EmployeeCode = e.Employee_code
        ORDER BY a.AllocationId DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def add_allocation(data):
    laptop_status = "Assigned" if data["AllocationType"] == "Onboarding" else "Available"
    
    if use_supabase:
        try:
            supabase_client.table("allocations").insert(data).execute()
            supabase_client.table("laptops").update({"Status": laptop_status}).eq("Laptop_SN_no", data["SerialNumber"]).execute()
            if data["AllocationType"] == "Offboarding":
                supabase_client.table("allocations").update({"Status": "Returned", "ReturnDate": data["HandoverDate"]}).eq("SerialNumber", data["SerialNumber"]).eq("Status", "Active").execute()
            return True
        except Exception as e:
            print(f"Supabase add_allocation error: {e}")
            raise e
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE laptops SET Status = ? WHERE Laptop_SN_no = ?", (laptop_status, data["SerialNumber"]))
        
        if data["AllocationType"] == "Offboarding":
            cursor.execute("""
                UPDATE allocations 
                SET Status = 'Returned', ReturnDate = ? 
                WHERE SerialNumber = ? AND Status = 'Active'
            """, (data["HandoverDate"], data["SerialNumber"]))
            
        cursor.execute("""
            INSERT INTO allocations (SerialNumber, EmployeeCode, AllocationType, HandoverDate, ReturnDate, HandoverBy, ReceivedBy, Condition, Status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data["SerialNumber"], data["EmployeeCode"], data["AllocationType"], data["HandoverDate"], data.get("ReturnDate"), data["HandoverBy"], data["ReceivedBy"], data["Condition"], data.get("Status", "Active")))
        
        conn.commit()
        success = True
    except Exception as e:
        conn.rollback()
        success = False
        raise e
    finally:
        conn.close()
    return success

def update_allocation(alloc_id, data):
    if use_supabase:
        try:
            supabase_client.table("allocations").update(data).eq("AllocationId", alloc_id).execute()
            return True
        except Exception as e:
            print(f"Supabase update_allocation error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    fields = ", ".join([f"{k} = ?" for k in data.keys()])
    values = list(data.values())
    values.append(alloc_id)
    cursor.execute(f"UPDATE allocations SET {fields} WHERE AllocationId = ?", values)
    conn.commit()
    conn.close()
    return True

# ==================== DAMAGE ISSUES CRUD ====================

def get_damage_issues():
    if use_supabase:
        try:
            res = supabase_client.table("damage_issues").select("*, laptops(Laptop_Brand), employees(Employee_full_name)").order("IssueId", desc=True).execute()
            
            flattened = []
            for item in res.data or []:
                flat_item = dict(item)
                laptop_rel = flat_item.pop("laptops", None) or {}
                flat_item["Laptop_Brand"] = laptop_rel.get("Laptop_Brand", "")
                
                emp_rel = flat_item.pop("employees", None) or {}
                flat_item["Employee_full_name"] = emp_rel.get("Employee_full_name", "")
                flattened.append(flat_item)
                
            return flattened
        except Exception as e:
            print(f"Supabase get_damage_issues error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.*, l.Laptop_Brand, e.Employee_full_name 
        FROM damage_issues d
        JOIN laptops l ON d.SerialNumber = l.Laptop_SN_no
        LEFT JOIN employees e ON d.EmployeeCode = e.Employee_code
        ORDER BY d.IssueId DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_damage_issue(issue_id):
    if use_supabase:
        try:
            res = supabase_client.table("damage_issues").select("*").eq("IssueId", issue_id).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            print(f"Supabase get_damage_issue error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM damage_issues WHERE IssueId = ?", (issue_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_damage_issue(data):
    ticket_status = data.get("Status", "Open")
    if ticket_status == "Resolved":
        laptop_status = "Active"
    elif ticket_status == "Scrapped":
        laptop_status = "EOL"
    else:
        laptop_status = "In Repair"
        
    if use_supabase:
        try:
            supabase_client.table("damage_issues").insert(data).execute()
            if laptop_status:
                supabase_client.table("laptops").update({"Status": laptop_status}).eq("Laptop_SN_no", data["SerialNumber"]).execute()
            return True
        except Exception as e:
            print(f"Supabase add_damage_issue error: {e}")
            raise e
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO damage_issues (SerialNumber, EmployeeCode, ReportedDate, Description, Severity, Status, ActionTaken, ResolutionDate, Cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data["SerialNumber"], data.get("EmployeeCode"), data["ReportedDate"], data["Description"], data["Severity"], data.get("Status", "Open"), data.get("ActionTaken"), data.get("ResolutionDate"), data.get("Cost", 0.0)))
        
        if laptop_status:
            cursor.execute("UPDATE laptops SET Status = ? WHERE Laptop_SN_no = ?", (laptop_status, data["SerialNumber"]))
            
        conn.commit()
        success = True
    except Exception as e:
        conn.rollback()
        success = False
        raise e
    finally:
        conn.close()
    return success

def update_damage_issue(issue_id, data):
    ticket_status = data.get("Status")
    laptop_status = None
    if ticket_status == "Resolved":
        laptop_status = "Active"
    elif ticket_status == "Scrapped":
        laptop_status = "EOL"
    elif ticket_status in ["In Repair", "Open"]:
        laptop_status = "In Repair"
        
    if use_supabase:
        try:
            issue_res = supabase_client.table("damage_issues").select("SerialNumber").eq("IssueId", issue_id).execute()
            sn = issue_res.data[0]["SerialNumber"] if issue_res.data else None
            
            supabase_client.table("damage_issues").update(data).eq("IssueId", issue_id).execute()
            if laptop_status and sn:
                supabase_client.table("laptops").update({"Status": laptop_status}).eq("Laptop_SN_no", sn).execute()
            return True
        except Exception as e:
            print(f"Supabase update_damage_issue error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT SerialNumber FROM damage_issues WHERE IssueId = ?", (issue_id,))
        sn_row = cursor.fetchone()
        sn = sn_row[0] if sn_row else None
        
        fields = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values())
        values.append(issue_id)
        cursor.execute(f"UPDATE damage_issues SET {fields} WHERE IssueId = ?", values)
        
        if laptop_status and sn:
            cursor.execute("UPDATE laptops SET Status = ? WHERE Laptop_SN_no = ?", (laptop_status, sn))
            
        conn.commit()
        success = True
    except Exception as e:
        conn.rollback()
        success = False
    finally:
        conn.close()
    return success

def delete_damage_issue(issue_id):
    if use_supabase:
        try:
            supabase_client.table("damage_issues").delete().eq("IssueId", issue_id).execute()
            return True
        except Exception as e:
            print(f"Supabase delete_damage_issue error: {e}")
            
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM damage_issues WHERE IssueId = ?", (issue_id,))
    conn.commit()
    conn.close()
    return True
