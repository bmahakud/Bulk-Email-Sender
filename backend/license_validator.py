import sys
import os
import subprocess
import hashlib
import hmac
import json
import base64
import requests
from datetime import datetime
from backend.database import Database

# Secret key used for signing licenses. 
# Keep the PRIVATE one on the web server. The client checks it using HMAC.
# For high security, we should run this inside PyArmor obfuscation.
LICENSE_HMAC_SECRET = b"ProMailerSecureActivationSecretKey2026!#"

# Default activation server URL (User can host this custom web admin panel)
DEFAULT_SERVER_URL = "https://promailer-licensing.diracai.com"

def get_machine_id() -> str:
    """Generates a unique hardware-based fingerprint for Windows/Linux machine."""
    try:
        if sys.platform == "win32":
            # Windows Unique Hardware UUID
            cmd = "wmic csproduct get uuid"
            output = subprocess.check_output(cmd, shell=True).decode()
            raw_id = output.split("\n")[1].strip()
        else:
            # Linux machine-id
            if os.path.exists("/etc/machine-id"):
                with open("/etc/machine-id", "r") as f:
                    raw_id = f.read().strip()
            else:
                raw_id = subprocess.check_output("cat /var/lib/dbus/machine-id", shell=True).decode().strip()
        return hashlib.sha256(raw_id.encode('utf-8')).hexdigest()
    except Exception:
        # Fallback to Mac Address UUID
        import uuid
        mac = str(uuid.getnode())
        return hashlib.sha256(mac.encode('utf-8')).hexdigest()

def verify_token(token_str: str) -> dict:
    """
    Decodes and verifies the cryptographic signature of the license token.
    Returns the payload dict if valid, throws ValueError/Exception if invalid or tampered.
    """
    try:
        # Step 1: Decode outer base64
        token_data = json.loads(base64.b64decode(token_str.encode('utf-8')).decode('utf-8'))
        payload = token_data["payload"]
        signature = base64.b64decode(token_data["signature"])
        
        # Step 2: Recalculate and compare the HMAC
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        expected_sig = hmac.new(LICENSE_HMAC_SECRET, payload_bytes, hashlib.sha256).digest()
        
        if not hmac.compare_digest(signature, expected_sig):
            raise ValueError("License signature is invalid or has been tampered with.")
            
        return payload
    except Exception as e:
        raise ValueError(f"Failed to verify license: {str(e)}")

def check_license_status() -> tuple[str, str]:
    """
    Checks the local database to see if the license is valid.
    Returns: (status, detail_message)
    Possible statuses:
        - "valid": Software is ready to run.
        - "no_license": No license is registered.
        - "machine_mismatch": License was transferred to another computer.
        - "expired": Expiration date has passed.
        - "clock_rollback": Local time tampering detected.
    """
    db = Database()
    token = db.get_setting("license_token", default="")
    last_run_str = db.get_setting("license_last_run", default="")
    
    if not token:
        return "no_license", "Application is not activated."
        
    try:
        payload = verify_token(token)
    except ValueError as e:
        return "no_license", str(e)
        
    # Check machine ID match
    current_machine = get_machine_id()
    if payload.get("machine_id") != current_machine:
        return "machine_mismatch", "This license is registered to another computer."
        
    # Check Expiration
    expiry_str = payload.get("expiry")
    try:
        expiry_date = datetime.fromisoformat(expiry_str)
    except Exception:
        return "no_license", "Invalid date format inside license payload."
        
    current_time = datetime.utcnow()
    
    if current_time >= expiry_date:
        return "expired", f"License expired on {expiry_date.strftime('%Y-%m-%d UTC')}."
        
    # Clock rollback detection
    if last_run_str:
        try:
            last_run = datetime.fromisoformat(last_run_str)
            if current_time < last_run:
                return "clock_rollback", "SYSTEM CLOCK TAMPERING DETECTED! Current time is earlier than the last run."
        except Exception:
            pass
            
    # Update last run time to prevent rollback next time
    db.set_setting("license_last_run", current_time.isoformat())
    return "valid", f"License active until {expiry_date.strftime('%Y-%m-%d')}."

def activate_license_online(license_key: str, server_url: str = DEFAULT_SERVER_URL) -> tuple[bool, str]:
    """
    Sends activation request to the web admin portal server.
    If success, saves returned license token to settings DB.
    """
    try:
        machine_id = get_machine_id()
        response = requests.post(
            f"{server_url.rstrip('/')}/api/activate",
            json={"license_key": license_key, "machine_id": machine_id},
            timeout=10
        )
        res_data = response.json()
        if response.status_code == 200 and res_data.get("status") == "success":
            db = Database()
            token = res_data.get("license_token")
            # Verify and save
            verify_token(token)
            db.set_setting("license_token", token)
            # Store initial run time
            db.set_setting("license_last_run", datetime.utcnow().isoformat())
            db.set_setting("license_server_used", server_url)
            return True, "Activation Successful!"
        else:
            return False, res_data.get("message", "Unknown error from server.")
    except requests.RequestException as e:
        return False, f"Could not connect to activation server: {str(e)}"
    except Exception as e:
        return False, f"Activation failed: {str(e)}"
