# ⚡ Quick Start - 5 Minutes to Sending

## Prerequisites Check
- [ ] Python 3.12+ installed
- [ ] Azure account (free tier is fine)
- [ ] Outlook/Hotmail account

---

## 🔥 Fast Setup (Copy-Paste Commands)

### 1. Register Azure App (5 mins)

Go to: https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade

1. Click "New registration"
2. Name: `OutlookMailer`
3. Account types: `Personal Microsoft accounts`
4. Redirect URI: `http://localhost:8000/callback`
5. Click Register
6. **Copy the "Application (client) ID"**
7. Go to "API permissions" → Add permission → Microsoft Graph → Delegated:
   - `Mail.Send`
   - `User.Read`
   - `offline_access`
8. Click "Add permissions"

### 2. Install & Run (2 mins)

```bash
# Navigate to project
cd "MAIL SENDER SOFTWARE PROJECT"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << 'EOF'
CLIENT_ID=YOUR_CLIENT_ID_HERE
CLIENT_SECRET=
TENANT_ID=common
REDIRECT_URI=http://localhost:8000/callback
LOG_LEVEL=INFO
DATABASE_PATH=database/database.db
EOF

# IMPORTANT: Edit .env and replace YOUR_CLIENT_ID_HERE with your actual client ID

# Run!
python app.py
```

### 3. Test Send (3 mins)

1. **Add Account**
   - Go to "Accounts" tab
   - Click "➕ Add Account"
   - Login with Outlook/Hotmail
   - Grant permissions

2. **Import Recipients**
   - Go to "Recipients" tab
   - Click "📥 Import CSV/Excel"
   - Select `uploads/csv/sample_recipients.csv`
   - Or use your own CSV with: `email,name,company,invoice`

3. **Load Template**
   - Go to "Templates" tab
   - Click "📂 Load HTML File"
   - Select `uploads/html/sample_template.html`
   - Add subjects (one per line):
     ```
     Invoice Ready
     Your Payment Details
     ```

4. **Send!**
   - Go to "Sender" tab
   - Click "🚀 Start Campaign"
   - Watch the magic happen! ✨

---

## 🎯 You're Done!

Check the **Logs** tab to see sent emails.

---

## ⚠️ Before Production Use

1. **Test with yourself**: Send to your own email first
2. **Check spam folder**: Ensure emails aren't flagged
3. **Add delays**: Use 1-2 second delays to avoid rate limits
4. **Multiple accounts**: Add 2-3 accounts for better throughput
5. **Compliance**: Only send to people who gave consent

---

## 🆘 Common Issues

**"Authentication failed"**
→ Check CLIENT_ID in .env file
→ Ensure redirect URI is exactly `http://localhost:8000/callback`

**"No active accounts"**
→ Add account in Accounts tab first

**"Rate limit exceeded"**
→ Normal! Software will automatically switch accounts
→ Add more accounts or increase delay

**"Module not found"**
→ Activate virtual environment: `source venv/bin/activate`
→ Install dependencies: `pip install -r requirements.txt`

---

## 📚 Full Documentation

- `SETUP_GUIDE.md` - Detailed setup instructions
- `PROJECT_STATUS.md` - Features and roadmap
- `README.md` - Project overview

---

**Happy Sending! 🚀📧**
