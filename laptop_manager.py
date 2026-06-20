import sqlite3
import os

DB_NAME = 'laptop_db.db'

def connect_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def show_all():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM laptops")
    rows = cursor.fetchall()
    
    print("\n--- Current Laptops in Database ---")
    print(f"{'S/N':<20} | {'Brand':<15} | {'Asset No':<15} | {'Status':<15}")
    print("-" * 75)
    for row in rows:
        print(f"{row['Laptop_SN_no']:<20} | {row['Laptop_Brand']:<15} | {row['Asset_number'] or '-':<15} | {row['Status']:<15}")
    conn.close()
    input("\nPress Enter to return to menu...")

def add_record():
    print("\n--- Add New Laptop ---")
    sn = input("Serial Number (Laptop_SN_no): ")
    try:
        no_val = input("No. (index): ")
        no = int(no_val) if no_val else None
    except ValueError:
        print("Invalid input for No. Must be a number.")
        return
        
    asset_number = input("Asset Number: ")
    rfid = input("RFID: ")
    brand = input("Brand (Laptop_Brand): ")
    purchase_date = input("Date of Purchase: ")
    eol_date = input("Date End of Life: ")
    warranty_type = input("Warranty Type: ")
    warranty_period = input("Warranty Period: ")
    status = input("Status [Available]: ") or "Available"

    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO laptops (Laptop_SN_no, No, Asset_number, RFID, Laptop_Brand, Date_of_Purchase, Date_end_of_life, Warranty_type, Warranty_period, Status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sn, no, asset_number, rfid, brand, purchase_date, eol_date, warranty_type, warranty_period, status))
        conn.commit()
        print("Record added successfully!")
    except sqlite3.IntegrityError:
        print("Error: Serial Number already exists.")
    conn.close()
    input("\nPress Enter to return to menu...")

def update_record():
    sn = input("\nEnter Serial Number of the laptop to update: ")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM laptops WHERE Laptop_SN_no = ?", (sn,))
    row = cursor.fetchone()
    
    if not row:
        print("Laptop not found.")
    else:
        row_dict = dict(row)
        print(f"Current details: {row_dict}")
        print("Enter new values (leave blank to keep current):")
        
        try:
            no_input = input(f"No [{row_dict['No']}]: ")
            no = int(no_input) if no_input else row_dict['No']
        except ValueError:
            print("Invalid input for No. Keeping current.")
            no = row_dict['No']

        asset_number = input(f"Asset Number [{row_dict['Asset_number']}]: ") or row_dict['Asset_number']
        rfid = input(f"RFID [{row_dict['RFID']}]: ") or row_dict['RFID']
        brand = input(f"Brand [{row_dict['Laptop_Brand']}]: ") or row_dict['Laptop_Brand']
        purchase_date = input(f"Purchase Date [{row_dict['Date_of_Purchase']}]: ") or row_dict['Date_of_Purchase']
        eol_date = input(f"EOL Date [{row_dict['Date_end_of_life']}]: ") or row_dict['Date_end_of_life']
        warranty_type = input(f"Warranty Type [{row_dict['Warranty_type']}]: ") or row_dict['Warranty_type']
        warranty_period = input(f"Warranty Period [{row_dict['Warranty_period']}]: ") or row_dict['Warranty_period']
        status = input(f"Status [{row_dict['Status']}]: ") or row_dict['Status']

        cursor.execute("""
            UPDATE laptops SET 
                No=?, Asset_number=?, RFID=?, Laptop_Brand=?, Date_of_Purchase=?, Date_end_of_life=?, Warranty_type=?, Warranty_period=?, Status=? 
            WHERE Laptop_SN_no=?
        """, (no, asset_number, rfid, brand, purchase_date, eol_date, warranty_type, warranty_period, status, sn))
        conn.commit()
        print("Record updated successfully!")
    conn.close()
    input("\nPress Enter to return to menu...")

def delete_record():
    sn = input("\nEnter Serial Number of the laptop to delete: ")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM laptops WHERE Laptop_SN_no = ?", (sn,))
    if cursor.rowcount > 0:
        conn.commit()
        print("Record deleted successfully!")
    else:
        print("Laptop not found.")
    conn.close()
    input("\nPress Enter to return to menu...")

def main():
    while True:
        clear_screen()
        print("====================================")
        print("    LAPTOP DATABASE MANAGER        ")
        print("====================================")
        print("1. View All Laptops")
        print("2. Add New Laptop")
        print("3. Update Laptop")
        print("4. Delete Laptop")
        print("5. Exit")
        choice = input("\nSelect an option (1-5): ")

        if choice == '1':
            show_all()
        elif choice == '2':
            add_record()
        elif choice == '3':
            update_record()
        elif choice == '4':
            delete_record()
        elif choice == '5':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    main()
