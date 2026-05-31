from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "secret_laptop_key"
DB_PATH = os.path.join(os.path.dirname(__file__), 'laptop_db.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    laptops = conn.execute('SELECT * FROM laptops').fetchall()
    conn.close()
    return render_template('index.html', laptops=laptops)

@app.route('/add', methods=('GET', 'POST'))
def add():
    if request.method == 'POST':
        sn = request.form['sn']
        brand = request.form['brand']
        model = request.form['model']
        chip = request.form['chip']
        warranty = request.form['warranty']
        cost = request.form['cost']
        screen = request.form['screen']
        ramrom = request.form['ramrom']

        if not sn:
            flash('Serial Number is required!')
        else:
            conn = get_db_connection()
            try:
                conn.execute('INSERT INTO laptops VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                             (sn, brand, model, chip, warranty, cost, screen, ramrom))
                conn.commit()
                conn.close()
                return redirect(url_for('index'))
            except sqlite3.IntegrityError:
                flash('Serial Number already exists!')
                conn.close()

    return render_template('add.html')

@app.route('/edit/<sn>', methods=('GET', 'POST'))
def edit(sn):
    conn = get_db_connection()
    laptop = conn.execute('SELECT * FROM laptops WHERE SerialNumber = ?', (sn,)).fetchone()

    if request.method == 'POST':
        brand = request.form['brand']
        model = request.form['model']
        chip = request.form['chip']
        warranty = request.form['warranty']
        cost = request.form['cost']
        screen = request.form['screen']
        ramrom = request.form['ramrom']

        conn.execute('UPDATE laptops SET Brand=?, Model=?, Chip=?, Warranty=?, Cost=?, ScreenSize=?, RamRom=? WHERE SerialNumber=?',
                     (brand, model, chip, warranty, cost, screen, ramrom, sn))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template('edit.html', laptop=laptop)

@app.route('/delete/<sn>')
def delete(sn):
    conn = get_db_connection()
    conn.execute('DELETE FROM laptops WHERE SerialNumber = ?', (sn,))
    conn.commit()
    conn.close()
    flash(f'Laptop {sn} deleted successfully.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
