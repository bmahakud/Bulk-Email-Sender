import os
import sys
import time
import pandas as pd
import msal
import requests
from dotenv import load_dotenv

# Load environmental variables
load_dotenv(override=True)

def check_accounts():
    excel_file = 'Test ID Advance mailer (1).xlsx'
    if not os.path.exists(excel_file):
        print(f"Error: {excel_file} not found in the directory.")
        return

    print(f"Reading accounts from {excel_file}...")
    try:
        # Read header=None since the sheet has no header row
        df = pd.read_excel(excel_file, header=None)
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return

    total_rows = len(df)
    print(f"Found {total_rows} entries in the sheet.")
    
    working_accounts = []
    failed_accounts = []

    for index, row in df.iterrows():
        line = str(row[0]).strip()
        if not line or '|' not in line:
            print(f"Row {index+1}: Invalid format (no pipe character found).")
            continue
            
        parts = line.split('|')
        if len(parts) < 4:
            print(f"Row {index+1}: Invalid format (expected 4 pipe-separated values, got {len(parts)}).")
            continue
            
        email = parts[0].strip()
        password = parts[1].strip()
        refresh_token = parts[2].strip()
        client_id = parts[3].strip()
        
        print(f"[{index+1}/{total_rows}] Verifying {email}... ", end="", flush=True)
        
        # Test auth
        try:
            authority = "https://login.microsoftonline.com/common"
            app = msal.PublicClientApplication(
                client_id=client_id,
                authority=authority
            )
            
            # Using the .default scope to get the consented permissions for these MSA tokens
            result = app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=["https://graph.microsoft.com/.default"]
            )
            
            if "access_token" in result:
                # Token refresh succeeded! Check scopes
                granted_scopes = result.get('scope', '')
                has_mail_send = "Mail.Send" in granted_scopes or "SMTP.Send" in granted_scopes
                
                if has_mail_send:
                    print("✅ WORKING (Mail.Send access confirmed)")
                    working_accounts.append({
                        "email": email,
                        "password": password,
                        "refresh_token": refresh_token,
                        "client_id": client_id,
                        "scopes": granted_scopes
                    })
                else:
                    print("⚠️ WARNING (Refresh succeeded but Mail.Send scope is missing)")
                    failed_accounts.append({
                        "email": email,
                        "error": "Missing Mail.Send/SMTP.Send permissions in granted scopes."
                    })
            else:
                err_desc = result.get('error_description') or result.get('error') or "Unknown MSAL Error"
                err_code = result.get('error', '')
                
                # Check for common error descriptions to make the output friendlier
                friendly_error = err_desc
                if "AADSTS50076" in err_desc:
                    friendly_error = "MFA required / Token expired"
                elif "AADSTS50173" in err_desc:
                    friendly_error = "Credential has expired or token expired"
                elif "AADSTS50057" in err_desc:
                    friendly_error = "User account is disabled / locked"
                elif "AADSTS50126" in err_desc:
                    friendly_error = "Invalid username or password"
                elif "AADSTS70000" in err_desc:
                    friendly_error = "Refresh token expired / revoked"
                
                print(f"❌ FAILED ({friendly_error})")
                failed_accounts.append({
                    "email": email,
                    "error": f"{err_code}: {friendly_error}"
                })
                
        except Exception as e:
            print(f"❌ ERROR ({str(e)})")
            failed_accounts.append({
                "email": email,
                "error": str(e)
            })
            
        # Small delay to avoid rate limiting during verification
        time.sleep(0.3)

    print("\n" + "="*50)
    print("Verification Summary:")
    print(f"Total Evaluated: {total_rows}")
    print(f"✅ Working: {len(working_accounts)}")
    print(f"❌ Failed: {len(failed_accounts)}")
    print("="*50)

    if working_accounts:
        print("\nWorking Accounts:")
        for a in working_accounts:
            print(f"- {a['email']} (Ready for campaigning)")
            
    if failed_accounts:
        print("\nFailed/Warning Accounts:")
        for a in failed_accounts:
            print(f"- {a['email']}: {a['error']}")

if __name__ == "__main__":
    check_accounts()
