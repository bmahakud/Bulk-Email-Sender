import os
import sqlite3
import hmac
import hashlib
import json
import base64
import uuid
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
DB_PATH = "licensing_server.db"
LICENSE_HMAC_SECRET = b"ProMailerSecureActivationSecretKey2026!#"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            customer_name TEXT,
            duration_days INTEGER NOT NULL,
            activated_at TEXT,
            expires_at TEXT,
            machine_id TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def sign_license_payload(payload: dict) -> str:
    # Sort keys to ensure deterministic JSON representation
    payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
    signature = hmac.new(LICENSE_HMAC_SECRET, payload_bytes, hashlib.sha256).digest()
    
    token_data = {
        "payload": payload,
        "signature": base64.b64encode(signature).decode('utf-8')
    }
    return base64.b64encode(json.dumps(token_data).encode('utf-8')).decode('utf-8')

# HTML Template for Web Admin Dashboard (Sleek dark theme)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ProMailer Pro | Licensing System Command Center</title>
    <style>
        :root {
            --bg-color: #12131a;
            --card-color: #1a1b27;
            --border-color: #252637;
            --text-color: #e8eaf0;
            --primary: #5865f2;
            --primary-hover: #4752c4;
            --success: #43b581;
            --danger: #ed4245;
            --warning: #f0a500;
        }
        body {
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            margin: 0;
            padding: 40px 20px;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--primary);
            padding-bottom: 20px;
            margin-bottom: 40px;
        }
        h1 {
            margin: 0;
            color: var(--primary);
            font-size: 28px;
            font-weight: 700;
        }
        h2 {
            font-size: 20px;
            margin-top: 0;
            margin-bottom: 20px;
        }
        .card {
            background-color: var(--card-color);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 24px;
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            font-size: 14px;
        }
        input, select {
            width: 100%;
            padding: 10px;
            background-color: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: white;
            box-sizing: border-box;
            font-size: 14px;
        }
        input:focus, select:focus {
            outline: none;
            border-color: var(--primary);
        }
        button {
            background-color: var(--primary);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
        }
        button:hover {
            background-color: var(--primary-hover);
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th, td {
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
        }
        th {
            background-color: var(--bg-color);
            font-weight: 600;
        }
        tr:hover {
            background-color: rgba(255, 255, 255, 0.02);
        }
        .status-badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-active {
            background-color: rgba(67, 181, 129, 0.2);
            color: var(--success);
        }
        .status-pending {
            background-color: rgba(240, 165, 0, 0.2);
            color: var(--warning);
        }
        .status-expired {
            background-color: rgba(237, 66, 69, 0.2);
            color: var(--danger);
        }
        .key-cell {
            font-family: 'Courier New', Courier, monospace;
            color: #00d4aa;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>✉ ProMailer Pro</h1>
                <div style="color: #7289da; font-size: 14px; margin-top: 5px;">Licensing System Control Panel</div>
            </div>
            <div>
                <span class="status-badge status-active">● Active Operations</span>
            </div>
        </header>

        <div class="card">
            <h2>🔑 Issue New License Key</h2>
            <form action="/admin/create" method="POST">
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px;">
                    <div class="form-group">
                        <label for="name">Customer/Client Name</label>
                        <input type="text" id="name" name="customer_name" required placeholder="e.g. John Doe Enterprises">
                    </div>
                    <div class="form-group">
                        <label for="duration">License Duration (Days)</label>
                        <input type="number" id="duration" name="duration_days" min="1" value="30" required placeholder="e.g. 30">
                    </div>
                    <div class="form-group" style="display: flex; align-items: flex-end;">
                        <button type="submit" style="width: 100%;">Create License Key</button>
                    </div>
                </div>
            </form>
        </div>

        <div class="card">
            <h2>📋 Active Licenses</h2>
            <table>
                <thead>
                    <tr>
                        <th>License Key</th>
                        <th>Client</th>
                        <th>Duration</th>
                        <th>Hardware Lock (ID)</th>
                        <th>Activated At</th>
                        <th>Expires At</th>
                        <th>Status</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {% for lic in licenses %}
                    <tr>
                        <td class="key-cell">{{ lic.license_key }}</td>
                        <td>{{ lic.customer_name }}</td>
                        <td>{{ lic.duration_days }} days</td>
                        <td style="font-size: 11px; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            {{ lic.machine_id or "Not Bound" }}
                        </td>
                        <td>{{ lic.activated_at or "-" }}</td>
                        <td>{{ lic.expires_at or "-" }}</td>
                        <td>
                            {% if not lic.activated_at %}
                                <span class="status-badge status-pending">Pending</span>
                            {% elif lic.is_expired %}
                                <span class="status-badge status-expired">Expired</span>
                            {% else %}
                                <span class="status-badge status-active">Active</span>
                            {% endif %}
                        </td>
                        <td>
                            <form action="/admin/delete/{{ lic.id }}" method="POST" style="margin:0;">
                                <button type="submit" style="background-color: var(--danger); padding: 6px 12px; font-size: 12px;">Delete</button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

# API ENDPOINT for activation request
@app.route('/api/activate', methods=['POST'])
def api_activate():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Missing JSON payload"}), 400
        
    license_key = data.get('license_key')
    machine_id = data.get('machine_id')
    
    if not license_key or not machine_id:
        return jsonify({"status": "error", "message": "Missing license_key or machine_id"}), 400

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM licenses WHERE license_key = ?", (license_key,))
    lic = cursor.fetchone()
    
    if not lic:
        conn.close()
        return jsonify({"status": "error", "message": "Invalid license key."}), 400
        
    # Check hardware lock binding
    if lic['machine_id'] and lic['machine_id'] != machine_id:
        conn.close()
        return jsonify({"status": "error", "message": "This license key is already bound to another computer."}), 400
        
    # Expiration Calculation
    activated_at = lic['activated_at']
    expires_at = lic['expires_at']
    
    if not activated_at:
        # First-time activation
        now_dt = datetime.utcnow()
        exp_dt = now_dt + timedelta(days=lic['duration_days'])
        
        activated_at = now_dt.isoformat()
        expires_at = exp_dt.isoformat()
        
        cursor.execute(
            "UPDATE licenses SET activated_at = ?, expires_at = ?, machine_id = ? WHERE id = ?",
            (activated_at, expires_at, machine_id, lic['id'])
        )
        conn.commit()
    else:
        # Already activated before, verify status is not expired
        exp_dt = datetime.fromisoformat(expires_at)
        if datetime.utcnow() >= exp_dt:
            conn.close()
            return jsonify({"status": "error", "message": "This license key has expired."}), 400

    conn.close()

    # Generate the cryptographic license token for local verification
    payload = {
        "license_key": license_key,
        "customer_name": lic["customer_name"],
        "machine_id": machine_id,
        "expiry": expires_at
    }
    
    token = sign_license_payload(payload)
    
    return jsonify({
        "status": "success",
        "license_token": token,
        "expiry": expires_at
    })

# ADMIN DASHBOARD ROUTES
@app.route('/admin')
def admin_dashboard():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM licenses ORDER BY id DESC")
    rows = cursor.fetchall()
    
    licenses = []
    now = datetime.utcnow()
    for row in rows:
        lic = dict(row)
        # Check if expired
        if lic['expires_at']:
            exp = datetime.fromisoformat(lic['expires_at'])
            lic['is_expired'] = now >= exp
        else:
            lic['is_expired'] = False
        licenses.append(lic)
        
    conn.close()
    return render_template_string(HTML_TEMPLATE, licenses=licenses)

@app.route('/admin/create', methods=['POST'])
def admin_create():
    customer_name = request.form.get('customer_name')
    duration_days = int(request.form.get('duration_days', 30))
    
    # Generate clean human-readable key format: PM-XXXX-XXXX-XXXX
    rand_chars = uuid.uuid4().hex.upper()
    license_key = f"PM-{rand_chars[:4]}-{rand_chars[4:8]}-{rand_chars[8:12]}"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO licenses (license_key, customer_name, duration_days) VALUES (?, ?, ?)",
        (license_key, customer_name, duration_days)
    )
    conn.commit()
    conn.close()
    
    return render_template_string(
        "<script>alert('Created License Key:\\n{{ key }}'); window.location.href='/admin';</script>",
        key=license_key
    )

@app.route('/admin/delete/<int:lic_id>', methods=['POST'])
def admin_delete(lic_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM licenses WHERE id = ?", (lic_id,))
    conn.commit()
    conn.close()
    return render_template_string("<script>window.location.href='/admin';</script>")

if __name__ == '__main__':
    init_db()
    print("--------------------------------------------------")
    print("ProMailer Board Web Server Admin Portal Running")
    print("Register keys here: http://localhost:5000/admin")
    print("--------------------------------------------------")
    app.run(host='0.0.0.0', port=5000, debug=True)
