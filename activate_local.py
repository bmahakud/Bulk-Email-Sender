import sys
import os
import hmac
import hashlib
import json
import base64
from datetime import datetime, timedelta
import sqlite3

# Import components from backend
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from backend.license_validator import get_machine_id, LICENSE_HMAC_SECRET
from backend.database import Database

def generate_local_activation(days=365):
    machine_id = get_machine_id()
    print(f"Detected Machine ID: {machine_id}")
    
    # Expiry 365 days in the future
    expiry_date = datetime.utcnow() + timedelta(days=days)
    expiry_str = expiry_date.isoformat()
    
    payload = {
        "license_key": "PM-LOCAL-BYPASS-ACTIVE",
        "customer_name": "Local developer / Tester",
        "machine_id": machine_id,
        "expiry": expiry_str
    }
    
    # Sign payload using the HMAC secret key
    payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
    signature = hmac.new(LICENSE_HMAC_SECRET, payload_bytes, hashlib.sha256).digest()
    
    token_dict = {
        "payload": payload,
        "signature": base64.b64encode(signature).decode('utf-8')
    }
    
    token_str = base64.b64encode(json.dumps(token_dict).encode('utf-8')).decode('utf-8')
    
    # Store in database
    db = Database()
    db.set_setting("license_token", token_str)
    db.set_setting("license_last_run", datetime.utcnow().isoformat())
    db.set_setting("license_server_used", "local_activation_bypass")
    
    print("\n" + "="*50)
    print("🔑 LOCAL ACTIVATION APPLIED SUCCESSFULLY")
    print(f"Expiry Date: {expiry_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Validity: {days} Days")
    print("="*50 + "\n")

if __name__ == "__main__":
    generate_local_activation()
