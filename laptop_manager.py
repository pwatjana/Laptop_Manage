import sqlite3
import os

DB_NAME = 'laptop_db.db'

def connect_db():
    return sqlite3.connect(DB_NAME)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def show_all():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM laptops")
    rows = cursor.fetchall()
    
    print("\n--- Current Laptops in Database ---")
    print(f"{'S/N':<10} | {'Brand':<10} | {'Model':<20} | {'Cost':<10}")
    print("-" * 60)
    for row in rows:
        print(f"{row[0]:<10} | {row[1]:<10} | {row[2]:<20} | {row[5]:<10}")
    conn.close()
    input("\nPress Enter to return to menu...")

def add_record():
    print("\n--- Add New Laptop ---")
    sn = input("Serial Number: ")
    brand = input("Brand: ")
    model = input("Model: ")
    chip = input("Chip: ")
    warranty = input("Warranty: ")
    try:
        cost = float(input("Cost: "))
        screen = float(input("Screen Size (inch): "))
    except ValueError:
        print("Invalid input for Cost or Screen Size. Must be numbers.")
        return
    ram_rom = input("Ram/Rom: ")

    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO laptops VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                       (sn, brand, model, chip, warranty, cost, screen, ram_rom))
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
    cursor.execute("SELECT * FROM laptops WHERE SerialNumber = ?", (sn,))
    row = cursor.fetchone()
    
    if not row:
        print("Laptop not found.")
    else:
        print(f"Current details: {row}")
        print("Enter new values (leave blank to keep current):")
        brand = input(f"Brand [{row[1]}]: ") or row[1]
        model = input(f"Model [{row[2]}]: ") or row[2]
        chip = input(f"Chip [{row[3]}]: ") or row[3]
        warranty = input(f"Warranty [{row[4]}]: ") or row[4]
        cost_input = input(f"Cost [{row[5]}]: ")
        cost = float(cost_input) if cost_input else row[5]
        screen_input = input(f"Screen Size [{row[6]}]: ")
        screen = float(screen_input) if screen_input else row[6]
        ram_rom = input(f"Ram/Rom [{row[7]}]: ") or row[7]

        cursor.execute("""UPDATE laptops SET 
                          Brand=?, Model=?, Chip=?, Warranty=?, Cost=?, ScreenSize=?, RamRom=? 
                          WHERE SerialNumber=?""", 
                       (brand, model, chip, warranty, cost, screen, ram_rom, sn))
        conn.commit()
        print("Record updated successfully!")
    conn.close()
    input("\nPress Enter to return to menu...")

def delete_record():
    sn = input("\nEnter Serial Number of the laptop to delete: ")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM laptops WHERE SerialNumber = ?", (sn,))
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
