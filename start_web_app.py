#!/usr/bin/env python3
"""
Launcher script and REST API server for the ProMailer Pro Web App (Light Theme)
"""
import os
import sys
import json
import time
import sqlite3
import threading
import http.server
import socketserver
import webbrowser

# Add project root to python load path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT_DIR)

from backend.database import Database
from backend.graph_api import GraphAPIClient
from backend.tag_processor import TagProcessor
from graph.auth import GraphAuth

def find_free_port(start_port=8080):
    import socket
    p = start_port
    while p < start_port + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", p))
                return p
            except OSError:
                p += 1
    return start_port

PORT = find_free_port(8080)
DIRECTORY = os.path.join(ROOT_DIR, 'web_app')

# ── CAMPAIGN EXECUTION SIMULATION & LIVE DISPATCH worker ──────────────────
class WebCampaignWorker:
    def __init__(self):
        self.db = Database()
        self.tag_proc = TagProcessor()
        self.status = "idle" # "idle", "running", "paused", "stopped"
        self._paused = False
        self.thread = None
        self.logs = []
        self.stats = {
            "sent": 0,
            "failed": 0,
            "remaining": 0,
            "current_smtp": "None"
        }
        
    def add_log(self, text, state=""):
        ts = time.strftime("%H:%M:%S")
        self.logs.append({"time": ts, "message": text, "type": state})
        print(f"[{ts}] {text}")
        if len(self.logs) > 500:
            self.logs.pop(0)

    def start(self, config):
        if self.status == "running":
            return False
        self.config = config
        self.status = "running"
        self._paused = False
        self.thread = threading.Thread(target=self.run_campaign)
        self.thread.daemon = True
        self.thread.start()
        return True

    def pause(self):
        if self.status == "running":
            self._paused = True
            self.status = "paused"
            self.add_log("[Task Engine] ⏸ Campaign paused.", "system-msg")
        elif self.status == "paused":
            self._paused = False
            self.status = "running"
            self.add_log("[Task Engine] ▶ Campaign resumed.", "system-msg")

    def stop(self):
        self.status = "stopped"
        self.add_log("[Task Engine] ⏹ Campaign terminated by administrator.", "error-msg")

    def run_campaign(self):
        self.add_log("[ENGINE] Handshaking Microsoft Graph API. Initializing thread context.", "system-msg")
        cfg = self.config
        
        # Load from DB
        smtp_accounts = self.db.get_smtp_accounts(status='ready')
        recipients = self.db.get_recipients(status='pending')
        
        if not smtp_accounts:
            self.add_log("[ENGINE] ❌ No ready SMTP accounts available. Aborting.", "error-msg")
            self.status = "idle"
            return
        if not recipients:
            self.add_log("[ENGINE] ❌ No pending recipients found. Aborting.", "error-msg")
            self.status = "idle"
            return

        total = len(recipients)
        self.stats = {"sent": 0, "failed": 0, "remaining": total, "current_smtp": "None"}
        
        delay_s = float(cfg.get('delay', 1.0))
        mode = cfg.get('smtp_mode', 'auto')
        limit_per_smtp = int(cfg.get('limit_per_smtp', 5))
        auto_remove = bool(cfg.get('auto_remove', True))
        
        subjects = cfg.get('subjects', ["Hello #NAME#"]) or ["Hello #NAME#"]
        senders = cfg.get('senders', [])
        default_sender = bool(cfg.get('default_sender', True))
        body_plain = cfg.get('body_plain', "")
        
        smtp_idx = 0
        smtp_sent_cnt = 0
        subj_idx = 0
        sndr_idx = 0
        
        recipients_queue = list(recipients)
        self.add_log(f"[ENGINE] 🚀 Starting | {len(smtp_accounts)} SMTP · {total} recipients | mode={mode} · delay={delay_s}s", "ready-msg")
        
        while recipients_queue and self.status in ("running", "paused"):
            if self.status == "stopped":
                break
            while self._paused and self.status == "paused":
                time.sleep(0.3)
            if self.status == "stopped":
                break
                
            # Verify SMTP left
            active_smtps = [s for s in smtp_accounts if s.get('status', 'ready') == 'ready']
            if not active_smtps:
                self.add_log("[ENGINE] ⚠ All SMTP accounts exhausted", "error-msg")
                break
                
            current_smtp = smtp_accounts[smtp_idx % len(smtp_accounts)]
            attempts = 0
            while current_smtp.get('status', 'ready') != 'ready' and attempts < len(smtp_accounts):
                smtp_idx += 1
                smtp_sent_cnt = 0
                current_smtp = smtp_accounts[smtp_idx % len(smtp_accounts)]
                attempts += 1
            if current_smtp.get('status', 'ready') != 'ready':
                self.add_log("[ENGINE] ⚠ No ready SMTP left", "error-msg")
                break
                
            self.stats["current_smtp"] = current_smtp['email']
            recipient = recipients_queue[0]
            graph = GraphAPIClient(current_smtp.get('client_id', ''))
            
            raw_subj = subjects[subj_idx % len(subjects)]
            sndr_name = senders[sndr_idx % len(senders)] if (senders and not default_sender) else ''
            
            # Form tags
            subject = self.tag_proc.process(raw_subj, recipient, {}, sender_name=sndr_name)
            to_name = self.tag_proc.process(sndr_name, recipient, {}, sender_name=sndr_name) if sndr_name else (recipient.get('name') or '')
            text_body = self.tag_proc.process(body_plain, recipient, {}, sender_name=sndr_name)
            text_as_html = f"<p style='font-family: Arial, sans-serif; font-size: 14px; white-space: pre-wrap;'>{text_body}</p>"
            
            # Refresh token
            try:
                auth = GraphAuth(client_id=current_smtp['client_id'])
                tokens = auth.refresh_access_token(current_smtp['token'])
                if not tokens or 'access_token' not in tokens:
                    raise ValueError("Refresh token was rejected or expired.")
                
                access_token = tokens['access_token']
                new_refresh = tokens.get('refresh_token', current_smtp['token'])
                
                if new_refresh != current_smtp['token']:
                    self.db.update_smtp_token(current_smtp['email'], new_refresh)
                    current_smtp['token'] = new_refresh
            except Exception as e:
                self.add_log(f"[ENGINE] ❌ Auth Error: Failed to refresh token for {current_smtp['email']}: {e}", "error-msg")
                if mode == 'auto':
                    self.add_log(f"[ENGINE] ⚠ [SWITCH] {current_smtp['email']} → next", "system-msg")
                    self.db.update_smtp_status(current_smtp['email'], 'error')
                    current_smtp['status'] = 'error'
                    smtp_idx += 1
                    smtp_sent_cnt = 0
                else:
                    self.stats["failed"] += 1
                    self.stats["remaining"] = len(recipients_queue) - 1
                    self.db.update_recipient_status(recipient['id'], 'failed', error_message=f"Auth Refresh Failed: {e}")
                    self.db.add_send_log(recipient['email'], current_smtp['email'], 'failed', 401, f"Auth Refresh Failed: {e}")
                    recipients_queue.pop(0)
                    subj_idx += 1
                    sndr_idx += 1
                continue

            self.add_log(f"[DISPATCH] Rotating slot [SMTP: {current_smtp['email']}] -> Sending to {recipient['email']}...")
            
            result = graph.send_email(
                access_token=access_token,
                to_email=recipient['email'],
                to_name=to_name,
                subject=subject,
                body_html=text_as_html
            )
            
            if result['success']:
                self.stats["sent"] += 1
                smtp_sent_cnt += 1
                self.add_log(f"[SUCCESS] Delivered to: '{recipient['email']}' via '{to_name or current_smtp['email']}' (Subject: {subject})", "success-msg")
                if auto_remove:
                    self.db.delete_recipient(recipient['id'])
                else:
                    self.db.update_recipient_status(recipient['id'], 'sent', current_smtp['email'])
                self.db.increment_smtp_sent(current_smtp['email'])
                self.db.add_send_log(recipient['email'], current_smtp['email'], 'sent')
                
                recipients_queue.pop(0)
                subj_idx += 1
                sndr_idx += 1
            else:
                ec = result.get('error_code', 0)
                em = result.get('error_message', 'Unknown error')
                
                if mode == 'auto' and (graph.is_auth_error(ec) or ec == 429):
                    self.add_log(f"[ENGINE] ❌ Sender Error on send via {current_smtp['email']} HTTP {ec}: {em} (Swapping sender...)", "error-msg")
                    self.db.update_smtp_status(current_smtp['email'], 'error')
                    current_smtp['status'] = 'error'
                    smtp_idx += 1
                    smtp_sent_cnt = 0
                    time.sleep(0.5)
                    continue
                else:
                    self.stats["failed"] += 1
                    self.add_log(f"[FAILURE] Bounced: {recipient['email']} | {em}", "error-msg")
                    self.db.update_recipient_status(recipient['id'], 'failed', error_message=em)
                    self.db.add_send_log(recipient['email'], current_smtp['email'], 'failed', ec, em)
                    
                    recipients_queue.pop(0)
                    subj_idx += 1
                    sndr_idx += 1

            if mode == 'limit' and smtp_sent_cnt >= limit_per_smtp:
                self.add_log(f"[ROTATOR] Limit of {limit_per_smtp} dispatches reached for {current_smtp['email']}. Switching slots.", "ready-msg")
                smtp_idx += 1
                smtp_sent_cnt = 0

            self.stats["remaining"] = len(recipients_queue)
            
            if delay_s > 0 and self.status == "running" and recipients_queue:
                time.sleep(delay_s)

        if self.status != "stopped":
            self.add_log(f"[COMPLETE] Campaign finished. Sent: {self.stats['sent']}, Failed: {self.stats['failed']}", "success-msg")
            self.status = "idle"


# Create Global worker instance
campaign_worker = WebCampaignWorker()


# ── REST API ROUTING HANDLER ──────────────────────────────────────────────
class APIRoutingHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # Prevent caching for APIs
        if self.path.startswith('/api'):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Content-Type', 'application/json')
        super().end_headers()

    def do_GET(self):
        if self.path.startswith('/api/'):
            self.handle_api_get()
        else:
            # Server static UI files
            super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api/'):
            self.handle_api_post()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_api_get(self):
        db = Database()
        
        # 1. GET /api/stats
        if self.path == '/api/stats':
            self.send_response(200)
            self.end_headers()
            stats = db.get_stats()
            self.wfile.write(json.dumps(stats).encode('utf-8'))
            
        # 2. GET /api/smtps
        elif self.path == '/api/smtps':
            self.send_response(200)
            self.end_headers()
            accounts = db.get_smtp_accounts()
            self.wfile.write(json.dumps(accounts).encode('utf-8'))
            
        # 3. GET /api/recipients
        elif self.path == '/api/recipients':
            self.send_response(200)
            self.end_headers()
            recs = db.get_recipients()
            self.wfile.write(json.dumps(recs).encode('utf-8'))
            
        # 4. GET /api/campaign/status
        elif self.path == '/api/campaign/status':
            self.send_response(200)
            self.end_headers()
            # Get latest UI logs
            payload = {
                "status": campaign_worker.status,
                "stats": campaign_worker.stats,
                "logs": campaign_worker.logs
            }
            self.wfile.write(json.dumps(payload).encode('utf-8'))
        else:
            self.send_error(404, "endpoint not found")

    def handle_api_post(self):
        db = Database()
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8')) if post_data else {}
        except Exception:
            data = {}

        # Helper method for direct SQL execution
        def execute_sql(query, params=()):
            conn = sqlite3.connect("data/mailer.db")
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            conn.close()

        # 1. POST /api/smtps/add
        if self.path == '/api/smtps/add':
            email = data.get('email')
            password = data.get('password', 'dummy_password')
            token = data.get('token')
            client_id = data.get('client_id')
            
            db.add_smtp_account(email, password, token, client_id)
            self.send_success_response({"message": "SMTP added successfully"})
            
        # 2. POST /api/smtps/delete
        elif self.path == '/api/smtps/delete':
            email = data.get('email')
            execute_sql("DELETE FROM smtp_accounts WHERE email = ?", (email,))
            self.send_success_response({"message": "SMTP deleted"})

        # 3. POST /api/smtps/clear
        elif self.path == '/api/smtps/clear':
            db.clear_smtp_accounts()
            self.send_success_response({"message": "All SMTPs cleared"})

        # 4. POST /api/recipients/add
        elif self.path == '/api/recipients/add':
            email = data.get('email')
            name = data.get('name', '')
            db.add_or_reset_recipient(email, name)
            self.send_success_response({"message": "Recipient added"})

        # 5. POST /api/recipients/delete
        elif self.path == '/api/recipients/delete':
            email = data.get('email')
            execute_sql("DELETE FROM recipients WHERE email = ?", (email,))
            self.send_success_response({"message": "Recipient deleted"})

        # 6. POST /api/recipients/clear
        elif self.path == '/api/recipients/clear':
            db.clear_recipients()
            self.send_success_response({"message": "Recipients cleared"})

        # 7. POST /api/campaign/start
        elif self.path == '/api/campaign/start':
            success = campaign_worker.start(data)
            self.send_success_response({"success": success, "status": campaign_worker.status})

        # 8. POST /api/campaign/pause
        elif self.path == '/api/campaign/pause':
            campaign_worker.pause()
            self.send_success_response({"status": campaign_worker.status})

        # 9. POST /api/campaign/stop
        elif self.path == '/api/campaign/stop':
            campaign_worker.stop()
            self.send_success_response({"status": campaign_worker.status})

        else:
            self.send_error(404, "Endpoint not found")

    def send_success_response(self, payload):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode('utf-8'))


def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), APIRoutingHandler) as httpd:
        print(f"📡 REST API Web Server running at http://localhost:{PORT}")
        print("Press Ctrl+C to terminate.")
        httpd.serve_forever()

def main():
    if not os.path.exists(DIRECTORY):
        print(f"Error: {DIRECTORY} directory not found.")
        sys.exit(1)
        
    # Start server in daemon thread
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # Give server a moment to bind
    time.sleep(1)
    
    # Open URL in browser
    url = f"http://localhost:{PORT}/index.html"
    print(f"🌐 Launching browser pointing to: {url}")
    webbrowser.open(url)
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Terminating Web App server. Goodbye!")

if __name__ == "__main__":
    main()
