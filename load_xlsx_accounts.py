import os
import sys
import pandas as pd
from backend.database import Database

def load_accounts():
    excel_file = 'Test ID Advance mailer (1).xlsx'
    if not os.path.exists(excel_file):
        print(f"Error: {excel_file} not found.")
        return
        
    print(f"Loading accounts from {excel_file} into the application database...")
    try:
        df = pd.read_excel(excel_file, header=None)
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return

    db = Database()
    loaded_count = 0

    for index, row in df.iterrows():
        line = str(row[0]).strip()
        if not line or '|' not in line:
            continue
            
        parts = line.split('|')
        if len(parts) < 4:
            continue
            
        email = parts[0].strip()
        password = parts[1].strip()
        refresh_token = parts[2].strip()
        client_id = parts[3].strip()
        
        # Add or update
        db.add_smtp_account(
            email=email,
            password=password,
            token=refresh_token,
            client_id=client_id
        )
        loaded_count += 1

    print("\n" + "="*50)
    print(f"✅ SUCCESS: Loaded {loaded_count} accounts into database.")
    print("Database path: data/mailer.db")
    print("="*50 + "\n")

if __name__ == "__main__":
    load_accounts()
