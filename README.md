# IT Inventory & Onboarding System

A Flask-based web application to manage corporate hardware assets, employee boarding (onboarding/offboarding allocations), and device damage or repair ticket tracking.

The application connects to **Supabase** as the primary online database and automatically falls back to a **local SQLite database** if the credentials are not provided or connection fails.

---

## 🛠️ Technology Stack

* **Backend**: Python, Flask, Jinja2 Templates
* **Database**: Supabase (PostgreSQL) / SQLite (Local)
* **Frontend**: HTML5, Vanilla CSS, Chart.js (Visual Analytics), FontAwesome Icons
* **Libraries**: `supabase-py`, `python-dotenv`, `flask-wtf` (CSRF Protection), `flask-talisman` (Security Headers), `bleach` (Input Sanitization)

---

## 🌟 Features & Recent Updates

### 1. Resource Dashboard Analytics
* **Date Range Filtering**: A top-level date range selector dynamically filters all stats cards, activity lists, and visual charts.
  * Links boarding history based on **Handover / Return Date**.
  * Links damage issues based on **Resolution Date** (or Reported Date for open issues).
* **Laptop Status Ratio (Doughnut Chart)**: Shows the real-time ratio of available/active, assigned, in repair, and EOL/scrapped laptops.
* **Damage Repair Cost (Stacked Bar Chart)**: Tracks historical repair costs grouped by **Resolution Month** (X-axis) and stacked dynamically by **Laptop Brand** (Color segments).

### 2. Laptops Pool Management
* **Advanced Filters**: Search and filter by Employee Name/Receiver, Section, Brand (searchable autocomplete), and Status (multiple select checkboxes).
* **CSV Export**: Instantly download the filtered subset of the laptop pool to a CSV file.
* **Status Synchronization Triggers**:
  * Reporting a new damage issue automatically shifts the laptop's status to **In Repair**.
  * Resolving the damage ticket reverts the laptop's status back to **Active**.
  * Scrapping a damaged laptop updates its status to **EOL**.
* **Boarding Validation**: The onboarding dropdown only displays laptops with an **Active / Available** status, preventing duplicate assignments.

### 3. Employee Directory
* **Full-text Filters**: Search and filter using any column (Employee Code, Full Name, Section, Join Date, Resign Date, and Status).
* **Status Rules**: Employees with no resign date or a resign date equal to `12/31/2069` are automatically flagged as **Active Duty**.
* **CSV Export**: Export employee directory listings (with formatted Active Duty/Offboarded status labels) directly to CSV.

---

## 📋 Database Schema

The database consists of 5 tables aligned with the import templates:

### 1. `laptops`
Stores hardware registration properties. (Aligned with `laptop.csv` columns)
* `Laptop_SN_no` (Text, Primary Key)
* `No` (Integer)
* `Asset_number` (Text)
* `RFID` (Text)
* `Laptop_Brand` (Text, Not Null)
* `Date_of_Purchase` (Text)
* `Date_end_of_life` (Text)
* `Warranty_type` (Text)
* `Warranty_period` (Text)
* `Status` (Text, Default: 'Available')

### 2. `employees`
Stores personnel profiles. (Aligned with `employee.csv` columns)
* `Employee_code` (Text, Primary Key)
* `Employee_full_name` (Text, Not Null)
* `Section` (Text)
* `Join_date` (Text)
* `Resign_Date` (Text)

### 3. `allocations`
Tracks the onboarding (laptop handovers) and offboarding (laptop returns) transactions.
* `AllocationId` (Integer, Primary Key)
* `SerialNumber` (Foreign Key referencing `laptops.Laptop_SN_no`)
* `EmployeeCode` (Foreign Key referencing `employees.Employee_code`)
* `AllocationType` (Text - 'Onboarding', 'Offboarding')
* `HandoverDate` (Text)
* `ReturnDate` (Text)
* `HandoverBy` (Text)
* `ReceivedBy` (Text)
* `Condition` (Text)
* `Status` (Text, Default: 'Active')

### 4. `damage_issues`
Logs maintenance incidents and repair tracking details.
* `IssueId` (Integer, Primary Key)
* `SerialNumber` (Foreign Key referencing `laptops.Laptop_SN_no`)
* `EmployeeCode` (Foreign Key referencing `employees.Employee_code`)
* `ReportedDate` (Text)
* `Description` (Text)
* `Severity` (Text - 'Low', 'Medium', 'High', 'Critical')
* `Status` (Text - 'Open', 'In Repair', 'Resolved', 'Scrapped')
* `ActionTaken` (Text)
* `ResolutionDate` (Text)
* `Cost` (Real, Default: 0.0)

### 5. `users`
Admin accounts for system authentication.
* `Username` (Text, Primary Key)
* `PasswordHash` (Text)
* `Role` (Text)

---

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have Python 3.8+ installed.

### 2. Installation
Clone this repository and install the dependencies listed in `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 3. Configuration (`.env`)
Create a `.env` file in the root folder (or use the existing one) with the following environment variables:
```env
FLASK_SECRET_KEY=highly_secure_random_string_987654321
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-api-key
```
*Note: If `SUPABASE_URL` or `SUPABASE_KEY` are missing or invalid, the app will automatically default to using local SQLite (`laptop_db.db`).*

### 4. Database Setup (Supabase)
Run the migration SQL script in your **Supabase SQL Editor** to initialize the tables, disable RLS, and grant API role privileges.

---

## 📥 Data Import (CSV Uploads)

If you need to upload initial data from `laptop.csv` and `employee.csv` into Supabase:
1. Ensure your `.env` contains valid credentials.
2. Put your `employee.csv` and `laptop.csv` in the root project folder.
3. Run the import script:
```bash
python import_csv_to_supabase.py
```

---

## 🏃 Running the Application

### Start the Flask Web Server
To launch the admin dashboard web application:
```bash
python app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

### Start the Local CLI Database Tool
To manage local SQLite records via a terminal-based CLI menu:
```bash
python laptop_manager.py
```

---

## 🔒 Security Features

1. **CSRF Protection**: Form submissions are protected using CSRF tokens generated by `Flask-WTF`.
2. **Security Headers**: Content Security Policy (CSP), HTTP Strict Transport Security (HSTS), and referrer rules are enforced via `Flask-Talisman`.
3. **Honeypot Fields**: Interactive forms contain a hidden input field (`website_url`) to trap spam bots; automated submissions filling this field are rejected with a `400 Bad Request`.
4. **Input Sanitization**: User-submitted text fields are sanitized via `bleach` to prevent Cross-Site Scripting (XSS) injections.

---

## 🔑 Default Credentials
* **Username**: `admin`
* **Password**: `admin123`
