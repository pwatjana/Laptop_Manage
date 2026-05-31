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
        return "Database not configured. Please check your environment variables.", 500
    try:
        response = supabase.table('laptops').select("*").execute()
        laptops = response.data
        return render_template('index.html', laptops=laptops)
    except Exception as e:
        return f"Error fetching data: {str(e)}", 500

@app.route('/add', methods=('GET', 'POST'))
def add():
    if request.method == 'POST':
        sn = request.form['sn']
        data = {
            "SerialNumber": sn,
            "Brand": request.form['brand'],
            "Model": request.form['model'],
            "Chip": request.form['chip'],
            "Warranty": request.form['warranty'],
            "Cost": float(request.form['cost']) if request.form['cost'] else 0,
            "ScreenSize": float(request.form['screen']) if request.form['screen'] else 0,
            "RamRom": request.form['ramrom']
        }

        if not sn:
            flash('Serial Number is required!')
        else:
            try:
                supabase.table('laptops').insert(data).execute()
                return redirect(url_for('index'))
            except Exception as e:
                flash(f'Error: {str(e)}')

    return render_template('add.html')

@app.route('/edit/<sn>', methods=('GET', 'POST'))
def edit(sn):
    response = supabase.table('laptops').select("*").eq("SerialNumber", sn).execute()
    laptop = response.data[0] if response.data else None

    if request.method == 'POST':
        data = {
            "Brand": request.form['brand'],
            "Model": request.form['model'],
            "Chip": request.form['chip'],
            "Warranty": request.form['warranty'],
            "Cost": float(request.form['cost']) if request.form['cost'] else 0,
            "ScreenSize": float(request.form['screen']) if request.form['screen'] else 0,
            "RamRom": request.form['ramrom']
        }
        supabase.table('laptops').update(data).eq("SerialNumber", sn).execute()
        return redirect(url_for('index'))

    return render_template('edit.html', laptop=laptop)

@app.route('/delete/<sn>')
def delete(sn):
    supabase.table('laptops').delete().eq("SerialNumber", sn).execute()
    flash(f'Laptop {sn} deleted successfully.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
