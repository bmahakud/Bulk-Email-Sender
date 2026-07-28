#!/usr/bin/env python3
"""
Interactive Auth Helper to generate login credentials for ProMailer Pro (run_pro.py)
"""
import os
import sys
from dotenv import load_dotenv

# Load env configurations
load_dotenv()

# Insert root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from graph.auth import GraphAuth

def main():
    print("==================================================")
    print("       Office 365 OAuth Token Generator          ")
    print("==================================================")
    
    client_id = os.getenv("CLIENT_ID")
    if not client_id or client_id == "your_client_id_here":
        print("[Error] Please make sure CLIENT_ID is correctly configured in your .env file.")
        sys.exit(1)
        
    print(f"Using Client ID: {client_id}")
    print("Launching browser login window... please sign in on the page that opens.")
    print("--------------------------------------------------")
    
    try:
        auth = GraphAuth()
        result = auth.acquire_token_interactive()
        
        if result and "access_token" in result:
            access_token = result["access_token"]
            refresh_token = result.get("refresh_token")
            
            if not refresh_token:
                print("[Warning] No refresh token returned! Ensure 'offline_access' scope is present in API permissions.")
                # We can fallback to access token inside the token placeholder
                refresh_token = access_token
                
            user_info = auth.get_user_info(access_token)
            email = "your-email@outlook.com"
            if user_info:
                email = user_info.get("userPrincipalName") or user_info.get("mail") or email
                
            print("\nSuccessfully Authenticated!")
            print("--- COPY the formatted line below ---")
            print(f"{email}|dummy_password|{refresh_token}|{client_id}")
            print("--------------------------------------")
            print("\nPaste this line inside your ProMailer Pro UI (run_pro.py)")
            print("under the 'SMTP' tab in SMTP single or bulk paste box.")
        else:
            print("[Error] Authentication failed. No token was acquired.")
            
    except Exception as e:
        print(f"\n[Error] Exception during authentication flow: {e}")

if __name__ == "__main__":
    main()
