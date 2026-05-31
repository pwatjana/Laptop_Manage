from flask import Flask, render_template, request, redirect, url_for, flash
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = "secret_laptop_key"

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
        data = {
            "SerialNumber": request.form['sn'],
            "Brand": request.form['brand'],
            "Model": request.form['model'],
            "Chip": request.form['chip'],
            "Warranty": request.form['warranty'],
            "Cost": float(request.form['cost']) if request.form['cost'] else 0,
            "ScreenSize": float(request.form['screen']) if request.form['screen'] else 0,
            "RamRom": request.form['ramrom']
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
        data = {
            "Brand": request.form['brand'], "Model": request.form['model'], "Chip": request.form['chip'],
            "Warranty": request.form['warranty'], "Cost": float(request.form['cost']),
            "ScreenSize": float(request.form['screen']), "RamRom": request.form['ramrom']
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
    laptops = supabase.table('laptops').select("SerialNumber, Brand, Model").execute().data
    if request.method == 'POST':
        data = {
            "EmployeeCode": request.form['code'],
            "FullName": request.form['name'],
            "SectionCode": request.form['section_code'],
            "SectionName": request.form['section_name'],
            "LaptopSN": request.form['laptop_sn'] if request.form['laptop_sn'] != "" else None,
            "JoinDate": request.form['join_date'] if request.form['join_date'] else None,
            "LastDate": request.form['last_date'] if request.form['last_date'] else None,
            "Remark": request.form['remark']
        }
        try:
            supabase.table('employees').insert(data).execute()
            return redirect(url_for('list_employees'))
        except Exception as e:
            flash(f'Error: {str(e)}')
    return render_template('add_employee.html', laptops=laptops)

@app.route('/employees/edit/<code>', methods=('GET', 'POST'))
def edit_employee(code):
    laptops = supabase.table('laptops').select("SerialNumber, Brand, Model").execute().data
    response = supabase.table('employees').select("*").eq("EmployeeCode", code).execute()
    emp = response.data[0] if response.data else None
    if request.method == 'POST':
        data = {
            "FullName": request.form['name'], "SectionCode": request.form['section_code'],
            "SectionName": request.form['section_name'], "LaptopSN": request.form['laptop_sn'] or None,
            "JoinDate": request.form['join_date'] or None, "LastDate": request.form['last_date'] or None,
            "Remark": request.form['remark']
        }
        supabase.table('employees').update(data).eq("EmployeeCode", code).execute()
        return redirect(url_for('list_employees'))
    return render_template('edit_employee.html', employee=emp, laptops=laptops)

@app.route('/employees/delete/<code>')
def delete_employee(code):
    supabase.table('employees').delete().eq("EmployeeCode", code).execute()
    return redirect(url_for('list_employees'))

if __name__ == '__main__':
    app.run(debug=True)
