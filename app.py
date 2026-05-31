from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from supabase import create_client, Client
import os
import bleach
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "highly_secure_random_string_123")

# Security 1: CSRF Protection
csrf = CSRFProtect(app)

# Security 2: Security Headers (CSP, HSTS, etc.)
# We allow inline styles for our demo, but in production, move CSS to files.
talisman = Talisman(app, content_security_policy={
    'default-src': '\'self\'',
    'style-src': ['\'self\'', '\'unsafe-inline\'']
})

# Supabase configuration
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

try:
    if not url or not key:
        print("Error: SUPABASE_URL or SUPABASE_KEY is missing.")
        supabase = None
    else:
        supabase: Client = create_client(url, key)
except Exception as e:
    print(f"Error initializing Supabase: {e}")
    supabase = None

def sanitize(data):
    """XSS Protection: Sanitize user input."""
    if isinstance(data, str):
        return bleach.clean(data)
    return data

def check_honeypot():
    """Honeypot Protection: Detect bots."""
    if request.form.get('website_url'):
        # If the hidden field is filled, it's likely a bot
        print("Honeypot triggered! Request rejected.")
        abort(400)

@app.route('/')
def index():
    if not supabase:
        return "Database not configured.", 500
    
    # Dashboard Data
    laptop_count = supabase.table('laptops').select("SerialNumber", count="exact").execute().count
    employee_count = supabase.table('employees').select("EmployeeCode", count="exact").execute().count
    
    return render_template('index.html', laptop_count=laptop_count, employee_count=employee_count)

# --- LAPTOP ROUTES ---

@app.route('/laptops')
def list_laptops():
    response = supabase.table('laptops').select("*").execute()
    return render_template('laptops.html', laptops=response.data)

@app.route('/laptops/add', methods=('GET', 'POST'))
def add_laptop():
    if request.method == 'POST':
        check_honeypot()
        data = {
            "SerialNumber": sanitize(request.form['sn']),
            "Brand": sanitize(request.form['brand']),
            "Model": sanitize(request.form['model']),
            "Chip": sanitize(request.form['chip']),
            "Status": sanitize(request.form['status']),
            "Warranty": sanitize(request.form['warranty']),
            "Cost": float(request.form['cost']) if request.form['cost'] else 0,
            "ScreenSize": float(request.form['screen']) if request.form['screen'] else 0,
            "RamRom": sanitize(request.form['ramrom'])
        }
        try:
            supabase.table('laptops').insert(data).execute()
            return redirect(url_for('list_laptops'))
        except Exception as e:
            flash(f'Error: {str(e)}')
    return render_template('add_laptop.html')

@app.route('/laptops/edit/<sn>', methods=('GET', 'POST'))
def edit_laptop(sn):
    response = supabase.table('laptops').select("*").eq("SerialNumber", sn).execute()
    laptop = response.data[0] if response.data else None
    if request.method == 'POST':
        check_honeypot()
        data = {
            "Brand": sanitize(request.form['brand']), 
            "Model": sanitize(request.form['model']), 
            "Chip": sanitize(request.form['chip']),
            "Status": sanitize(request.form['status']),
            "Warranty": sanitize(request.form['warranty']), 
            "Cost": float(request.form['cost']),
            "ScreenSize": float(request.form['screen']), 
            "RamRom": sanitize(request.form['ramrom'])
        }
        supabase.table('laptops').update(data).eq("SerialNumber", sn).execute()
        return redirect(url_for('list_laptops'))
    return render_template('edit_laptop.html', laptop=laptop)

@app.route('/laptops/delete/<sn>')
def delete_laptop(sn):
    supabase.table('laptops').delete().eq("SerialNumber", sn).execute()
    return redirect(url_for('list_laptops'))

# --- EMPLOYEE ROUTES ---

@app.route('/employees')
def list_employees():
    response = supabase.table('employees').select("*").execute()
    return render_template('employees.html', employees=response.data)

@app.route('/employees/add', methods=('GET', 'POST'))
def add_employee():
    if request.method == 'POST':
        check_honeypot()
        data = {
            "EmployeeCode": sanitize(request.form['code']),
            "FullName": sanitize(request.form['name']),
            "SectionCode": sanitize(request.form['section_code']),
            "SectionName": sanitize(request.form['section_name']),
            "JoinDate": request.form['join_date'] if request.form['join_date'] else None,
            "LastDate": request.form['last_date'] if request.form['last_date'] else None,
            "Remark": sanitize(request.form['remark'])
        }
        try:
            supabase.table('employees').insert(data).execute()
            return redirect(url_for('list_employees'))
        except Exception as e:
            flash(f'Error: {str(e)}')
    return render_template('add_employee.html')

@app.route('/employees/edit/<code>', methods=('GET', 'POST'))
def edit_employee(code):
    response = supabase.table('employees').select("*").eq("EmployeeCode", code).execute()
    emp = response.data[0] if response.data else None
    if request.method == 'POST':
        check_honeypot()
        data = {
            "FullName": sanitize(request.form['name']), 
            "SectionCode": sanitize(request.form['section_code']),
            "SectionName": sanitize(request.form['section_name']), 
            "JoinDate": request.form['join_date'] or None, 
            "LastDate": request.form['last_date'] or None,
            "Remark": sanitize(request.form['remark'])
        }
        supabase.table('employees').update(data).eq("EmployeeCode", code).execute()
        return redirect(url_for('list_employees'))
    return render_template('edit_employee.html', employee=emp)

@app.route('/employees/delete/<code>')
def delete_employee(code):
    supabase.table('employees').delete().eq("EmployeeCode", code).execute()
    return redirect(url_for('list_employees'))

if __name__ == '__main__':
    app.run(debug=True)
