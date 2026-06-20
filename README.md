# IT Inventory & Onboarding System

A Flask-based web application to manage corporate hardware assets, employee on/offboarding allocations, and device damage or repair ticket tracking.

The application connects to **Supabase** (PostgreSQL) as the primary online database and automatically falls back to a **local SQLite mirror** if the connection is unavailable.

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.8+, Flask, Jinja2 |
| Database (Primary) | Supabase (PostgreSQL) |
| Database (Fallback) | SQLite (`laptop_db.db`) |
| Frontend | HTML5, Vanilla CSS, Chart.js, FontAwesome |
| Security | Flask-WTF (CSRF), Flask-Talisman (CSP/HSTS), bleach (XSS) |

---

## 🌟 Features

### 📊 Resource Dashboard
- **Date Range Filter** — Filters all stats, charts, and activity feeds simultaneously
  - Boarding records linked by **Handover / Return Date**
  - Damage issues linked by **Resolution Date** (or Reported Date for open tickets)
- **Laptop Status Doughnut Chart** — Live ratio of Available, Assigned, In Repair, and EOL assets
- **Repair Cost Stacked Bar Chart** — Monthly repair costs stacked by laptop brand

### 💻 Laptop Pool Management
- Search and filter by Employee Name, Section, Brand (autocomplete), and Status (multi-select)
- **CSV Export** of any filtered view
- **Automatic status sync triggers**:
  - Damage reported → laptop moves to **In Repair**
  - Damage resolved → laptop reverts to **Active**
  - Damage scrapped → laptop moves to **EOL**
- Onboarding dropdown shows only **Active / Available** laptops

### 👥 Employee Directory
- Filter by any column: Code, Name, Section, Join Date, Resign Date, Status
- Employees with no resign date or `12/31/2069` are displayed as **Active Duty**
- **CSV Export** with human-readable status labels

### 🔄 On/Offboarding Allocations
- Full handover and return tracking per laptop per employee
- Allocation history with type badges (Onboarding / Offboarding)

### 🔧 Damage & Repair Tracking
- Severity levels: Low / Medium / High / Critical
- Status lifecycle: Open → In Repair → Resolved / Scrapped
- Cost tracking per ticket with aggregated dashboard totals

---

## 📋 Database Schema

### `laptops`
| Column | Type | Notes |
|---|---|---|
| `Laptop_SN_no` | TEXT (PK) | Serial Number |
| `No` | INTEGER | Asset sequence number |
| `Asset_number` | TEXT | Asset tag |
| `RFID` | TEXT | RFID tag |
| `Laptop_Brand` | TEXT | e.g. Dell, Lenovo, HP |
| `Date_of_Purchase` | TEXT | |
| `Date_end_of_life` | TEXT | |
| `Warranty_type` | TEXT | |
| `Warranty_period` | TEXT | |
| `Status` | TEXT | Available / Assigned / In Repair / EOL |

### `employees`
| Column | Type | Notes |
|---|---|---|
| `Employee_code` | TEXT (PK) | |
| `Employee_full_name` | TEXT | |
| `Section` | TEXT | Department / section |
| `Join_date` | TEXT | |
| `Resign_Date` | TEXT | `12/31/2069` = Active Duty |

### `allocations`
| Column | Type | Notes |
|---|---|---|
| `AllocationId` | INTEGER (PK) | Auto-increment |
| `SerialNumber` | TEXT (FK) | → `laptops.Laptop_SN_no` |
| `EmployeeCode` | TEXT (FK) | → `employees.Employee_code` |
| `AllocationType` | TEXT | Onboarding / Offboarding |
| `HandoverDate` | TEXT | |
| `ReturnDate` | TEXT | |
| `HandoverBy` | TEXT | Logged-in admin username |
| `ReceivedBy` | TEXT | Recipient name |
| `Condition` | TEXT | |
| `Status` | TEXT | Active / Returned |

### `damage_issues`
| Column | Type | Notes |
|---|---|---|
| `IssueId` | INTEGER (PK) | Auto-increment |
| `SerialNumber` | TEXT (FK) | → `laptops.Laptop_SN_no` |
| `EmployeeCode` | TEXT (FK) | → `employees.Employee_code` |
| `ReportedDate` | TEXT | |
| `Description` | TEXT | |
| `Severity` | TEXT | Low / Medium / High / Critical |
| `Status` | TEXT | Open / In Repair / Resolved / Scrapped |
| `ActionTaken` | TEXT | |
| `ResolutionDate` | TEXT | |
| `Cost` | REAL | Repair cost in THB |

### `users`
| Column | Type | Notes |
|---|---|---|
| `Username` | TEXT (PK) | |
| `PasswordHash` | TEXT | Werkzeug PBKDF2 hash |
| `Role` | TEXT | e.g. Admin |

---

## 🚀 Getting Started

### 1. Prerequisites
```bash
# Python 3.8 or higher required
python --version
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
Create a `.env` file in the project root:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-anon-key
FLASK_SECRET_KEY=your-strong-random-secret-key
```

> **Generate a secure `FLASK_SECRET_KEY`:**
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

> **Note:** If Supabase credentials are missing or the connection fails, the app automatically falls back to the local `laptop_db.db` SQLite database.

### 4. Database Setup (Supabase)
Run the migration SQL in your **Supabase SQL Editor** to create all tables, disable RLS, and grant API access.

### 5. Sync Local SQLite from Supabase
To populate the local fallback database with the current Supabase data:
```bash
python sync_sqlite_from_supabase.py
```
This drops the old `laptop_db.db`, recreates the correct schema, and imports all records from Supabase.

### 6. Create Admin User
On first run the app automatically seeds a default admin into the local SQLite. For Supabase, use `db_helper.create_admin_user()`:
```bash
python -c "import db_helper; db_helper.create_admin_user('your_username', 'your_password')"
```

> ⚠️ **Never commit credentials to version control.** The `.env` file is in `.gitignore`.

---

## 📥 CSV Data Import

To bulk-load laptops and employees from CSV into Supabase:
1. Place `laptop.csv` and `employee.csv` in the project root.
2. Ensure `.env` has valid Supabase credentials.
3. Run:
```bash
python import_csv_to_supabase.py
```

---

## 🏃 Running the Application

### Flask Web Server
```bash
python app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser.

### Local CLI Tool
```bash
python laptop_manager.py
```
### Render.com
https://laptop-manage-board.onrender.com/
---

## 🔒 Security

| Control | Implementation |
|---|---|
| CSRF Protection | Flask-WTF tokens on every POST form |
| Security Headers | Flask-Talisman (CSP, HSTS, X-Frame-Options) |
| Password Hashing | Werkzeug PBKDF2-SHA256 |
| Input Sanitization | `bleach.clean()` on all user input |
| SQL Injection | Parameterized queries throughout `db_helper.py` |
| XSS | Jinja2 autoescaping + bleach sanitization |
| Bot Detection | Honeypot field (`website_url`) on all forms |
| Secrets | Loaded from `.env` only — never hardcoded |
| CDN Allowlist | Only `cdnjs.cloudflare.com` and Google Fonts in CSP |

> **Credentials are not stored in this repository.** Contact the system administrator for access.
