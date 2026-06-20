from flask import Flask, render_template, request, redirect, url_for, flash, abort, session
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
import os
import bleach
from dotenv import load_dotenv
from functools import wraps

# Load environment variables
load_dotenv()

# Import our custom DB Helper
import db_helper

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "highly_secure_random_string_987654321")

# Security 1: CSRF Protection
csrf = CSRFProtect(app)

# Security 2: Security Headers (Allowing Google Fonts and font icons)
talisman = Talisman(app, content_security_policy={
    'default-src': '\'self\'',
    'style-src': [
        '\'self\'', 
        '\'unsafe-inline\'', 
        'https://fonts.googleapis.com', 
        'https://cdnjs.cloudflare.com'
    ],
    'font-src': [
        '\'self\'', 
        'https://fonts.gstatic.com', 
        'https://cdnjs.cloudflare.com',
        'data:'
    ],
    'script-src': [
        '\'self\'', 
        '\'unsafe-inline\'',
        'https://cdnjs.cloudflare.com'
    ]
})

def sanitize(data):
    """XSS Protection: Sanitize user input."""
    if isinstance(data, str):
        return bleach.clean(data.strip())
    return data

def check_honeypot():
    """Honeypot Protection: Detect automated bots on form submissions."""
    if request.form.get('website_url'):
        print("Honeypot field was filled. Bot detected.")
        abort(400)

def admin_required(f):
    """Authorization decorator for admin-only routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user'):
            flash("Admin authentication required.", "danger")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_user():
    """Inject current logged-in user into templates."""
    return dict(current_user=session.get('user'))

# --- AUTH ROUTES ---

@app.route('/login', methods=('GET', 'POST'))
def login():
    if session.get('user'):
        return redirect(url_for('index'))
        
    next_url = request.args.get('next')
    if request.method == 'POST':
        check_honeypot()
        username = sanitize(request.form.get('username'))
        password = request.form.get('password')
        
        user = db_helper.authenticate_admin(username, password)
        if user:
            session['user'] = user
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(next_url or url_for('index'))
        else:
            flash("Invalid username or password.", "danger")
            
    return render_template('login.html', next=next_url)

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# --- DASHBOARD ---

@app.route('/')
def index():
    # Read date parameters
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()
    
    from datetime import datetime
    def parse_date(date_str):
        if not date_str:
            return None
        date_str = str(date_str).strip()
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%Y-%m-%d %H:%M:%S'):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                pass
        return None

    start_date = parse_date(start_date_str)
    end_date = parse_date(end_date_str)
    
    # Fetch all data
    laptops = db_helper.get_laptops()
    allocations = db_helper.get_allocations()
    damages = db_helper.get_damage_issues()
    
    # Keep laptops unfiltered by purchase date to show full pool status and ratio
    filtered_laptops = laptops
        
    # Filter Allocations (by Handover / Return Date)
    filtered_allocations = []
    for a in allocations:
        # Check HandoverDate primarily, and ReturnDate if it is a Returned/Offboarding record
        h_date = parse_date(a.get("HandoverDate"))
        r_date = parse_date(a.get("ReturnDate"))
        
        # Link handover date or return date for boarding
        primary_date = h_date
        if a.get("AllocationType") == "Offboarding":
            primary_date = h_date
        elif a.get("Status") == "Returned" and r_date:
            # If onboarding is returned, return date is also relevant
            primary_date = r_date
            
        if start_date:
            if not primary_date or primary_date < start_date:
                continue
        if end_date:
            if not primary_date or primary_date > end_date:
                continue
        filtered_allocations.append(a)
        
    # Filter Damages (by ResolutionDate if resolved, or ReportedDate if not resolved)
    filtered_damages = []
    for d in damages:
        # Link resolved date for damage report
        d_date = parse_date(d.get("ResolutionDate"))
        if not d_date:
            # Fallback to reported date for unresolved issues
            d_date = parse_date(d.get("ReportedDate"))
            
        if start_date:
            if not d_date or d_date < start_date:
                continue
        if end_date:
            if not d_date or d_date > end_date:
                continue
        filtered_damages.append(d)
        
    # Compute dashboard statistics on the filtered subsets
    stats = {
        "total_laptops": len(filtered_laptops),
        "available_laptops": sum(1 for l in filtered_laptops if l.get("Status") in ["Available", "Active"]),
        "assigned_laptops": sum(1 for l in filtered_laptops if l.get("Status") == "Assigned"),
        "repair_laptops": sum(1 for l in filtered_laptops if l.get("Status") == "In Repair"),
        "scrapped_laptops": sum(1 for l in filtered_laptops if l.get("Status") in ["Scrapped", "EOL"]),
        "total_employees": len(db_helper.get_employees()),
        "active_allocations": sum(1 for a in filtered_allocations if a.get("Status") == "Active"),
        "open_damages": sum(1 for d in filtered_damages if d.get("Status") in ["Open", "In Repair"]),
        "total_repair_cost": sum(float(d.get("Cost") or 0.0) for d in filtered_damages)
    }
    
    # Group resolved damages for Stacked Bar Chart
    # X-axis: resolution month, Y-axis: repair cost, segment: laptop brand
    resolved_damages = [d for d in filtered_damages if d.get("Status") == "Resolved" and d.get("ResolutionDate")]
    
    brand_month_cost = {}
    all_months = set()
    all_brands = set()
    
    for d in resolved_damages:
        r_date = parse_date(d.get("ResolutionDate"))
        if not r_date:
            continue
        month_str = r_date.strftime("%Y-%m")
        brand = d.get("Laptop_Brand") or "Unknown"
        cost = float(d.get("Cost") or 0.0)
        
        all_months.add(month_str)
        all_brands.add(brand)
        
        if brand not in brand_month_cost:
            brand_month_cost[brand] = {}
        brand_month_cost[brand][month_str] = brand_month_cost[brand].get(month_str, 0.0) + cost
        
    sorted_months = sorted(list(all_months))
    
    # Bright theme stack colors
    colors = [
        'rgba(99, 102, 241, 0.75)',   # Indigo
        'rgba(16, 185, 129, 0.75)',   # Emerald
        'rgba(245, 158, 11, 0.75)',   # Amber
        'rgba(239, 68, 68, 0.75)',    # Rose/Red
        'rgba(59, 130, 246, 0.75)',   # Blue
        'rgba(167, 139, 250, 0.75)',  # Violet
        'rgba(236, 72, 153, 0.75)',   # Pink
        'rgba(14, 165, 233, 0.75)',   # Sky
    ]
    border_colors = [
        '#6366f1', '#10b981', '#f59e0b', '#ef4444', '#3b82f6', '#a78bfa', '#ec4899', '#0ea5e9'
    ]
    
    chart_datasets = []
    for idx, brand in enumerate(sorted(list(all_brands))):
        color_idx = idx % len(colors)
        data_points = []
        for month in sorted_months:
            data_points.append(brand_month_cost[brand].get(month, 0.0))
            
        chart_datasets.append({
            "label": brand,
            "data": data_points,
            "backgroundColor": colors[color_idx],
            "borderColor": border_colors[color_idx],
            "borderWidth": 1.5
        })
        
    # Get top 5 filtered records for the dashboard activity feed
    recent_allocs = filtered_allocations[:5]
    recent_dams = filtered_damages[:5]
    
    return render_template(
        'index.html', 
        stats=stats, 
        recent_allocations=recent_allocs,
        recent_damages=recent_dams,
        db_type="Online Supabase" if db_helper.use_supabase else "Local SQLite",
        start_date=start_date_str,
        end_date=end_date_str,
        chart_months=sorted_months,
        chart_datasets=chart_datasets,
        pie_labels=["Available / Active", "Assigned", "In Repair", "Scrapped / EOL"],
        pie_values=[
            stats["available_laptops"],
            stats["assigned_laptops"],
            stats["repair_laptops"],
            stats["scrapped_laptops"]
        ]
    )

# --- LAPTOP ROUTES ---

import csv
import io
from flask import Response

@app.route('/laptops')
def list_laptops():
    search_name = sanitize(request.args.get('name', '')).strip()
    search_section = sanitize(request.args.get('section', '')).strip()
    search_brand = sanitize(request.args.get('brand', '')).strip()
    selected_statuses = request.args.getlist('status')
    show_all = request.args.get('all', 'false') == 'true'
    
    # Fetch unique values for searchable datalists
    all_laptops = db_helper.get_laptops()
    unique_brands = sorted(list(set(l["Laptop_Brand"] for l in all_laptops if l.get("Laptop_Brand"))))
    
    all_employees = db_helper.get_employees()
    unique_names = sorted(list(set(e["Employee_full_name"] for e in all_employees if e.get("Employee_full_name"))))
    unique_sections = sorted(list(set(e["Section"] for e in all_employees if e.get("Section"))))
    
    laptops = []
    has_searched = bool(search_name or search_section or search_brand or show_all or selected_statuses)
    
    if has_searched:
        all_allocations = db_helper.get_allocations()
        
        # Filter active allocations (Onboarding/Assign)
        active_allocs = {}
        for a in all_allocations:
            if a["Status"] == "Active" and a["AllocationType"] == "Onboarding":
                active_allocs[a["SerialNumber"]] = a
                
        enriched_laptops = []
        for laptop in all_laptops:
            sn = laptop["Laptop_SN_no"]
            alloc = active_allocs.get(sn)
            laptop_dict = dict(laptop)
            if alloc:
                laptop_dict["Employee_code"] = alloc.get("EmployeeCode", "")
                laptop_dict["Employee_name"] = alloc.get("Employee_full_name", "")
                laptop_dict["Received_by"] = alloc.get("ReceivedBy", "")
            else:
                laptop_dict["Employee_code"] = ""
                laptop_dict["Employee_name"] = ""
                laptop_dict["Received_by"] = ""
            enriched_laptops.append(laptop_dict)
            
        emp_sections = {e["Employee_code"]: e.get("Section", "") for e in all_employees}
        
        for l in enriched_laptops:
            code = l.get("Employee_code")
            l["Section"] = emp_sections.get(code, "") if code else ""
            
        filtered_laptops = []
        for l in enriched_laptops:
            # Filter by brand
            if search_brand and search_brand.lower() not in l["Laptop_Brand"].lower():
                continue
            # Filter by status (multiple select checkboxes)
            if selected_statuses and l.get("Status") not in selected_statuses:
                continue
            # Filter by name
            if search_name:
                name_match = False
                if l["Employee_name"] and search_name.lower() in l["Employee_name"].lower():
                    name_match = True
                elif l["Received_by"] and search_name.lower() in l["Received_by"].lower():
                    name_match = True
                if not name_match:
                    continue
            # Filter by section
            if search_section and search_section.lower() not in l["Section"].lower():
                continue
            filtered_laptops.append(l)
            
        laptops = filtered_laptops
        
    return render_template(
        'laptops.html', 
        laptops=laptops, 
        has_searched=has_searched,
        search_name=search_name,
        search_section=search_section,
        search_brand=search_brand,
        selected_statuses=selected_statuses,
        unique_brands=unique_brands,
        unique_names=unique_names,
        unique_sections=unique_sections,
        show_all=show_all
    )

@app.route('/laptops/export')
def export_laptops():
    search_name = sanitize(request.args.get('name', '')).strip()
    search_section = sanitize(request.args.get('section', '')).strip()
    search_brand = sanitize(request.args.get('brand', '')).strip()
    selected_statuses = request.args.getlist('status')
    show_all = request.args.get('all', 'false') == 'true'
    
    all_laptops = db_helper.get_laptops()
    all_allocations = db_helper.get_allocations()
    
    active_allocs = {}
    for a in all_allocations:
        if a["Status"] == "Active" and a["AllocationType"] == "Onboarding":
            active_allocs[a["SerialNumber"]] = a
            
    enriched_laptops = []
    for laptop in all_laptops:
        sn = laptop["Laptop_SN_no"]
        alloc = active_allocs.get(sn)
        laptop_dict = dict(laptop)
        if alloc:
            laptop_dict["Employee_code"] = alloc.get("EmployeeCode", "")
            laptop_dict["Employee_name"] = alloc.get("Employee_full_name", "")
            laptop_dict["Received_by"] = alloc.get("ReceivedBy", "")
        else:
            laptop_dict["Employee_code"] = ""
            laptop_dict["Employee_name"] = ""
            laptop_dict["Received_by"] = ""
        enriched_laptops.append(laptop_dict)
        
    all_employees = db_helper.get_employees()
    emp_sections = {e["Employee_code"]: e.get("Section", "") for e in all_employees}
    
    for l in enriched_laptops:
        code = l.get("Employee_code")
        l["Section"] = emp_sections.get(code, "") if code else ""
        
    filtered_laptops = []
    for l in enriched_laptops:
        if search_brand and search_brand.lower() not in l["Laptop_Brand"].lower():
            continue
        if selected_statuses and l.get("Status") not in selected_statuses:
            continue
        if search_name:
            name_match = False
            if l["Employee_name"] and search_name.lower() in l["Employee_name"].lower():
                name_match = True
            elif l["Received_by"] and search_name.lower() in l["Received_by"].lower():
                name_match = True
            if not name_match:
                continue
        if search_section and search_section.lower() not in l["Section"].lower():
            continue
        filtered_laptops.append(l)
        
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow([
        "Laptop SN", "No", "Asset Number", "RFID", "Brand", 
        "Purchase Date", "EOL Date", "Warranty Type", "Warranty Period", 
        "Status", "Employee Code", "Employee Name", "Section"
    ])
    
    for l in filtered_laptops:
        cw.writerow([
            l.get("Laptop_SN_no", ""),
            l.get("No", ""),
            l.get("Asset_number", ""),
            l.get("RFID", ""),
            l.get("Laptop_Brand", ""),
            l.get("Date_of_Purchase", ""),
            l.get("Date_end_of_life", ""),
            l.get("Warranty_type", ""),
            l.get("Warranty_period", ""),
            l.get("Status", ""),
            l.get("Employee_code", ""),
            l.get("Employee_name", ""),
            l.get("Section", "")
        ])
        
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=filtered_laptops.csv"}
    )

@app.route('/laptops/add', methods=('GET', 'POST'))
@admin_required
def add_laptop():
    if request.method == 'POST':
        check_honeypot()
        try:
            data = {
                "Laptop_SN_no": sanitize(request.form['sn']),
                "No": int(request.form['no']) if request.form['no'] else None,
                "Asset_number": sanitize(request.form['asset_number']),
                "RFID": sanitize(request.form['rfid']),
                "Laptop_Brand": sanitize(request.form['brand']),
                "Date_of_Purchase": sanitize(request.form['purchase_date']),
                "Date_end_of_life": sanitize(request.form['eol_date']),
                "Warranty_type": sanitize(request.form['warranty_type']),
                "Warranty_period": sanitize(request.form['warranty_period']),
                "Status": sanitize(request.form['status'])
            }
            db_helper.add_laptop(data)
            flash("Laptop successfully added to inventory.", "success")
            return redirect(url_for('list_laptops'))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            
    return render_template('add_laptop.html')

@app.route('/laptops/edit/<sn>', methods=('GET', 'POST'))
@admin_required
def edit_laptop(sn):
    laptop = db_helper.get_laptop(sn)
    if not laptop:
        flash("Laptop not found.", "danger")
        return redirect(url_for('list_laptops'))
        
    if request.method == 'POST':
        check_honeypot()
        data = {
            "No": int(request.form['no']) if request.form['no'] else None,
            "Asset_number": sanitize(request.form['asset_number']),
            "RFID": sanitize(request.form['rfid']),
            "Laptop_Brand": sanitize(request.form['brand']),
            "Date_of_Purchase": sanitize(request.form['purchase_date']),
            "Date_end_of_life": sanitize(request.form['eol_date']),
            "Warranty_type": sanitize(request.form['warranty_type']),
            "Warranty_period": sanitize(request.form['warranty_period']),
            "Status": sanitize(request.form['status'])
        }
        db_helper.update_laptop(sn, data)
        flash("Laptop details updated successfully.", "success")
        return redirect(url_for('list_laptops'))
        
    return render_template('edit_laptop.html', laptop=laptop)

@app.route('/laptops/delete/<sn>')
@admin_required
def delete_laptop(sn):
    try:
        db_helper.delete_laptop(sn)
        flash("Laptop removed from inventory.", "success")
    except Exception as e:
        flash(f"Error deleting laptop: {str(e)}", "danger")
    return redirect(url_for('list_laptops'))

# --- EMPLOYEE ROUTES ---

@app.route('/employees')
def list_employees():
    search_code = sanitize(request.args.get('code', '')).strip()
    search_name = sanitize(request.args.get('name', '')).strip()
    search_section = sanitize(request.args.get('section', '')).strip()
    search_join_date = sanitize(request.args.get('join_date', '')).strip()
    search_resign_date = sanitize(request.args.get('resign_date', '')).strip()
    search_status = sanitize(request.args.get('status', '')).strip()
    
    all_employees = db_helper.get_employees()
    
    # Extract unique sections, join dates, and resign dates for searchable datalists
    unique_sections = sorted(list(set(e["Section"] for e in all_employees if e.get("Section"))))
    unique_join_dates = sorted(list(set(e["Join_date"] for e in all_employees if e.get("Join_date"))))
    unique_resign_dates = sorted(list(set(e["Resign_Date"] for e in all_employees if e.get("Resign_Date"))))
    
    filtered_employees = []
    for e in all_employees:
        if search_code and search_code.lower() not in e["Employee_code"].lower():
            continue
        if search_name and search_name.lower() not in e["Employee_full_name"].lower():
            continue
        if search_section and e.get("Section") and search_section.lower() not in e["Section"].lower():
            continue
        if search_join_date and e.get("Join_date") and search_join_date.lower() not in e["Join_date"].lower():
            continue
        if search_resign_date and e.get("Resign_Date") and search_resign_date.lower() not in e["Resign_Date"].lower():
            continue
            
        # Status logic matching UI
        is_active = not e.get("Resign_Date") or e.get("Resign_Date") == "12/31/2069"
        if search_status == "Active" and not is_active:
            continue
        if search_status == "Offboarded" and is_active:
            continue
            
        filtered_employees.append(e)
        
    return render_template(
        'employees.html', 
        employees=filtered_employees,
        search_code=search_code,
        search_name=search_name,
        search_section=search_section,
        search_join_date=search_join_date,
        search_resign_date=search_resign_date,
        search_status=search_status,
        unique_sections=unique_sections,
        unique_join_dates=unique_join_dates,
        unique_resign_dates=unique_resign_dates
    )

@app.route('/employees/export')
def export_employees():
    search_code = sanitize(request.args.get('code', '')).strip()
    search_name = sanitize(request.args.get('name', '')).strip()
    search_section = sanitize(request.args.get('section', '')).strip()
    search_join_date = sanitize(request.args.get('join_date', '')).strip()
    search_resign_date = sanitize(request.args.get('resign_date', '')).strip()
    search_status = sanitize(request.args.get('status', '')).strip()
    
    all_employees = db_helper.get_employees()
    
    filtered_employees = []
    for e in all_employees:
        if search_code and search_code.lower() not in e["Employee_code"].lower():
            continue
        if search_name and search_name.lower() not in e["Employee_full_name"].lower():
            continue
        if search_section and e.get("Section") and search_section.lower() not in e["Section"].lower():
            continue
        if search_join_date and e.get("Join_date") and search_join_date.lower() not in e["Join_date"].lower():
            continue
        if search_resign_date and e.get("Resign_Date") and search_resign_date.lower() not in e["Resign_Date"].lower():
            continue
            
        is_active = not e.get("Resign_Date") or e.get("Resign_Date") == "12/31/2069"
        if search_status == "Active" and not is_active:
            continue
        if search_status == "Offboarded" and is_active:
            continue
            
        filtered_employees.append(e)
        
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Employee Code", "Full Name", "Section", "Join Date", "Resign Date", "Status"])
    
    for e in filtered_employees:
        is_active = not e.get("Resign_Date") or e.get("Resign_Date") == "12/31/2069"
        status_str = "Active Duty" if is_active else "Offboarded"
        resign_str = e.get("Resign_Date") if not is_active else ""
        
        cw.writerow([
            e.get("Employee_code", ""),
            e.get("Employee_full_name", ""),
            e.get("Section", ""),
            e.get("Join_date", ""),
            resign_str,
            status_str
        ])
        
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=filtered_employees.csv"}
    )

@app.route('/employees/add', methods=('GET', 'POST'))
@admin_required
def add_employee():
    if request.method == 'POST':
        check_honeypot()
        try:
            data = {
                "Employee_code": sanitize(request.form['code']),
                "Employee_full_name": sanitize(request.form['name']),
                "Section": sanitize(request.form['section']),
                "Join_date": request.form['join_date'] if request.form['join_date'] else None,
                "Resign_Date": request.form['resign_date'] if request.form['resign_date'] else None
            }
            db_helper.add_employee(data)
            flash("Employee record created.", "success")
            return redirect(url_for('list_employees'))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            
    return render_template('add_employee.html')

@app.route('/employees/edit/<code>', methods=('GET', 'POST'))
@admin_required
def edit_employee(code):
    emp = db_helper.get_employee(code)
    if not emp:
        flash("Employee not found.", "danger")
        return redirect(url_for('list_employees'))
        
    if request.method == 'POST':
        check_honeypot()
        data = {
            "Employee_full_name": sanitize(request.form['name']), 
            "Section": sanitize(request.form['section']),
            "Join_date": request.form['join_date'] or None, 
            "Resign_Date": request.form['resign_date'] or None
        }
        db_helper.update_employee(code, data)
        flash("Employee details updated.", "success")
        return redirect(url_for('list_employees'))
        
    return render_template('edit_employee.html', employee=emp)

@app.route('/employees/delete/<code>')
@admin_required
def delete_employee(code):
    try:
        db_helper.delete_employee(code)
        flash("Employee record deleted.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    return redirect(url_for('list_employees'))

# --- ONBOARDING / OFFBOARDING (ALLOCATION) ROUTES ---

@app.route('/allocations')
def list_allocations():
    allocations = db_helper.get_allocations()
    return render_template('allocations.html', allocations=allocations)

@app.route('/allocations/add', methods=('GET', 'POST'))
@admin_required
def add_allocation():
    laptops = db_helper.get_laptops()
    employees = db_helper.get_employees()
    
    if request.method == 'POST':
        check_honeypot()
        try:
            data = {
                "SerialNumber": sanitize(request.form['sn']),
                "EmployeeCode": sanitize(request.form['employee_code']),
                "AllocationType": sanitize(request.form['type']),
                "HandoverDate": request.form['handover_date'],
                "HandoverBy": session['user']['username'],
                "ReceivedBy": sanitize(request.form['received_by']),
                "Condition": sanitize(request.form['condition']),
                "Status": "Active" if request.form['type'] == "Onboarding" else "Returned"
            }
            
            # Additional validation
            laptop = db_helper.get_laptop(data["SerialNumber"])
            if data["AllocationType"] == "Onboarding" and laptop and laptop["Status"] == "Assigned":
                flash(f"Warning: Laptop {data['SerialNumber']} is already marked as Assigned. Proceeding anyway.", "info")
                
            db_helper.add_allocation(data)
            flash(f"Allocation record saved. Laptop status set to {'Assigned' if data['AllocationType'] == 'Onboarding' else 'Available'}.", "success")
            return redirect(url_for('list_allocations'))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            
    return render_template('add_allocation.html', laptops=laptops, employees=employees)

# --- DAMAGE ISSUES ROUTES ---

@app.route('/damage_issues')
def list_damage_issues():
    issues = db_helper.get_damage_issues()
    return render_template('damage_issues.html', issues=issues)

@app.route('/damage_issues/add', methods=('GET', 'POST'))
@admin_required
def add_damage_issue():
    laptops = db_helper.get_laptops()
    employees = db_helper.get_employees()
    
    if request.method == 'POST':
        check_honeypot()
        try:
            data = {
                "SerialNumber": sanitize(request.form['sn']),
                "EmployeeCode": sanitize(request.form['employee_code']) or None,
                "ReportedDate": request.form['reported_date'],
                "Description": sanitize(request.form['description']),
                "Severity": sanitize(request.form['severity']),
                "Status": sanitize(request.form['status']),
                "ActionTaken": sanitize(request.form['action_taken']),
                "Cost": float(request.form['cost']) if request.form['cost'] else 0.0,
                "ResolutionDate": request.form['resolution_date'] or None
            }
            db_helper.add_damage_issue(data)
            flash("Damage ticket filed and saved.", "success")
            return redirect(url_for('list_damage_issues'))
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
            
    return render_template('add_damage_issue.html', laptops=laptops, employees=employees)

@app.route('/damage_issues/edit/<int:issue_id>', methods=('GET', 'POST'))
@admin_required
def edit_damage_issue(issue_id):
    issue = db_helper.get_damage_issue(issue_id)
    if not issue:
        flash("Damage ticket not found.", "danger")
        return redirect(url_for('list_damage_issues'))
        
    if request.method == 'POST':
        check_honeypot()
        data = {
            "Description": sanitize(request.form['description']),
            "Severity": sanitize(request.form['severity']),
            "Status": sanitize(request.form['status']),
            "ActionTaken": sanitize(request.form['action_taken']),
            "Cost": float(request.form['cost']) if request.form['cost'] else 0.0,
            "ResolutionDate": request.form['resolution_date'] or None
        }
        db_helper.update_damage_issue(issue_id, data)
        flash("Damage ticket updated successfully.", "success")
        return redirect(url_for('list_damage_issues'))
        
    return render_template('edit_damage_issue.html', issue=issue)

@app.route('/damage_issues/delete/<int:issue_id>')
@admin_required
def delete_damage_issue(issue_id):
    try:
        db_helper.delete_damage_issue(issue_id)
        flash("Damage ticket deleted.", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    return redirect(url_for('list_damage_issues'))

if __name__ == '__main__':
    app.run(debug=True)
