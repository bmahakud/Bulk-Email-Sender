import sys
import msal
import webbrowser
from backend.database import Database

def main():
    client_id = "9e5f94bc-e8a4-4e73-b8be-63364c29d753"
    email = "poojagupta@diracaipvtltd.onmicrosoft.com"
    pwd = "Diracai@2026#"

    print("\n" + "="*60)
    print("  Microsoft 365 Business Account Authorization")
    print(f"  Target: {email}")
    print("="*60 + "\n")

    app = msal.PublicClientApplication(
        client_id,
        authority="https://login.microsoftonline.com/common"
    )

    scopes = [
        "https://outlook.office.com/SMTP.Send",
        "https://graph.microsoft.com/Mail.Send",
        "https://graph.microsoft.com/User.Read"
    ]

    flow = app.initiate_device_flow(scopes=scopes)
    if "user_code" not in flow:
        print("❌ Error initiating login flow:", flow)
        return

    user_code = flow["user_code"]
    url = flow.get("verification_uri", "https://login.microsoft.com/device")

    print(f"👉 Step 1: In your browser, go to: {url}")
    print(f"👉 Step 2: Enter this 9-character code:  {user_code}")
    print(f"👉 Step 3: Sign in with {email} and click 'Accept'.\n")
    
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print("⏳ Waiting for you to finish sign-in in your browser...")
    result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        refresh_token = result.get("refresh_token") or result.get("access_token")
        db = Database()
        db.add_smtp_account(email, pwd, refresh_token, client_id)
        print("\n" + "✅"*25)
        print(f"🎉 SUCCESS! {email} is now linked to ProMailer!")
        print("It can now send thousands of emails directly to inboxes!")
        print("✅"*25 + "\n")
    else:
        print("\n❌ Authorization failed:", result.get("error_description") or result.get("error"))

if __name__ == "__main__":
    main()

