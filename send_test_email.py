import os
import sys
import msal
import requests
from dotenv import load_dotenv
from backend.database import Database
from backend.graph_api import GraphAPIClient
from graph.auth import GraphAuth

# Load environment variable files
load_dotenv(override=True)

def send_test(to_email):
    db = Database()
    accounts = db.get_smtp_accounts(status='ready')
    
    if not accounts:
        print("Error: No ready SMTP accounts found in the database. Run load_xlsx_accounts.py first.")
        return
        
    # Use the first account in the list to test
    sender_account = accounts[0]
    sender_email = sender_account['email']
    client_id = sender_account['client_id']
    refresh_token = sender_account['token']
    
    print("="*60)
    print("📧 PROMAILER PRO - CLI END-TO-END SEND TEST")
    print("="*60)
    print(f"From Sender Account: {sender_email}")
    print(f"To Recipient Email: {to_email}")
    print(f"Using Client ID:    {client_id}")
    print("Refreshing OAuth authentication tokens...")
    
    try:
        # 1. Refresh auth token using the database client ID and refresh token
        auth = GraphAuth(client_id=client_id)
        tokens = auth.refresh_access_token(refresh_token)
        
        if not tokens or 'access_token' not in tokens:
            raise ValueError("Token refresh was rejected. Refresh token might be expired/revoked.")
            
        access_token = tokens['access_token']
        new_refresh = tokens.get('refresh_token', refresh_token)
        
        # Keep DB updated if token updated
        if new_refresh != refresh_token:
            db.update_smtp_token(sender_email, new_refresh)
            print("Status: Regained fresh refresh token and updated database.")
        else:
            print("Status: Token successfully refreshed.")
            
        # 2. Build test email content
        subject = "ProMailer Pro - System Verification Test"
        body_html = """
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; border-radius: 8px; padding: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.05);">
                    <h2 style="color: #5865f2; margin-top: 0;">✓ End-to-End System Test Successful!</h2>
                    <p>Hello,</p>
                    <p>This email confirms that the <b>Outlook Bulk Mail Sender (ProMailer Pro)</b> is working correctly on your machine.</p>
                    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                    <h3>Technical Test Details:</h3>
                    <ul>
                        <li><b>Sender Account:</b> {sender_email}</li>
                        <li><b>Auth Engine:</b> MSAL OAuth2 (Microsoft Graph API)</li>
                        <li><b>Verification status:</b> SUCCESS</li>
                    </ul>
                    <p style="font-size: 12px; color: #777; margin-top: 30px;">Sent automatically by the ProMailer system verification tool.</p>
                </div>
            </body>
        </html>
        """.format(sender_email=sender_email)
        
        # 3. Send email using Graph API
        print("Sending test email via Microsoft Graph API...")
        graph_client = GraphAPIClient(client_id=client_id)
        
        result = graph_client.send_email(
            access_token=access_token,
            to_email=to_email,
            to_name="ProMailer Verifier",
            subject=subject,
            body_html=body_html
        )
        
        print("\n" + "="*50)
        if result.get('success'):
            print("🎉 SUCCESS: Email successfully sent!")
            print("Check your recipient inbox (including spam folder) for the test mail.")
            db.increment_smtp_sent(sender_email)
        else:
            print("❌ FAILED TO SEND EMAIL:")
            print(f"Error Code: {result.get('error_code')}")
            print(f"Message:    {result.get('error_message')}")
        print("="*50 + "\n")
        
    except Exception as e:
        print(f"\n❌ CRITICAL SYSTEM ERROR DURING TEST: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Missing target recipient email address.")
        print("Usage: python3 send_test_email.py <recipient_email>")
        sys.exit(1)
        
    target_recipient = sys.argv[1].strip()
    send_test(target_recipient)
