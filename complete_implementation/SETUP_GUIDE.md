# Outlook Bulk Mail Sender - Complete Setup Guide

## 📋 Prerequisites

- Python 3.12 or higher
- Microsoft Azure account (free)
- Windows/Linux/macOS

---

## 🚀 Step 1: Azure App Registration

### 1.1 Create Azure AD Application

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **New registration**

**Registration Details:**
- **Name**: `Outlook Mail Sender`
- **Supported account types**: 
  - Select: `Accounts in any organizational directory and personal Microsoft accounts`
- **Redirect URI**: 
  - Platform: `Public client/native (mobile & desktop)`
  - URI: `http://localhost:8000/callback`
4. Click **Register**

### 1.2 Copy Credentials

After registration:
1. Copy **Application (client) ID** - you'll need this
2. Copy **Directory (tenant) ID** - you'll need this

### 1.3 Add API Permissions

1. Go to **API permissions** (left menu)
2. Click **Add a permission**
3. Select **Microsoft Graph**
4. Select **Delegated permissions**
5. Add these permissions:
   - `Mail.Send` - Send email as the user
   - `User.Read` - Read user profile
   - `offline_access` - Maintain access to data
6. Click **Add permissions**
7. Click **Grant admin consent** (if available)

---

## 🐍 Step 2: Python Environment Setup

### 2.1 Create Virtual Environment

```bash
# Navigate to project directory
cd "MAIL SENDER SOFTWARE PROJECT"

# Create virtual environment
python3.12 -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 2.2 Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## ⚙️ Step 3: Configuration

### 3.1 Create .env File

Create a file named `.env` in the project root:

```bash
cp .env.example .env
```

### 3.2 Edit .env File

Open `.env` and add your Azure credentials:

```env
# Microsoft Graph API Configuration
CLIENT_ID=your_application_client_id_here
CLIENT_SECRET=
TENANT_ID=common
REDIRECT_URI=http://localhost:8000/callback

# Application Settings
LOG_LEVEL=INFO
DATABASE_PATH=database/database.db
```

**Important:**
- Replace `your_application_client_id_here` with the **Application (client) ID** from Step 1.2
- Leave `CLIENT_SECRET` empty (not needed for public client)
- Keep `TENANT_ID=common` for personal Microsoft accounts
- If using only organizational accounts, replace `common` with your tenant ID

---

## 🎯 Step 4: First Run

### 4.1 Run the Application

```bash
python app.py
```

### 4.2 Add Your First Account

1. Application window opens
2. Go to **Accounts** tab
3. Click **➕ Add Account**
4. Browser opens for Microsoft login
5. Sign in with your Outlook/Hotmail account
6. Grant permissions when prompted
7. Account appears in the table with status "active"

---

## 📧 Step 5: Send Your First Campaign

### 5.1 Add Recipients

1. Go to **Recipients** tab
2. Click **📥 Import CSV/Excel**
3. Select your CSV file with columns:
   ```
   email,name,company,invoice
   john@example.com,John Doe,ACME Corp,INV-001
   jane@example.com,Jane Smith,Tech Ltd,INV-002
   ```
4. Recipients appear in table

### 5.2 Create HTML Template

1. Go to **Templates** tab
2. Click **📂 Load HTML File** or paste HTML directly
3. Add subject lines (one per line):
   ```
   Invoice Ready
   Your Payment Details
   Download Invoice
   ```
4. Use tags in your HTML:
   - `#EMAIL#` - Recipient email
   - `#NAME#` - Recipient name
   - `#COMPANY#` - Company name
   - `#INVOICE#` - Invoice number
   - `#DATE#` - Current date
   
**Example HTML:**
```html
<!DOCTYPE html>
<html>
<body>
    <h2>Hello #NAME#,</h2>
    <p>Your invoice #INVOICE# is ready.</p>
    <p>Company: #COMPANY#</p>
    <p>Date: #DATE#</p>
</body>
</html>
```

### 5.3 Start Campaign

1. Go to **Sender** tab
2. Set delay between emails (default: 1 second)
3. Set retry count (default: 3)
4. Click **🚀 Start Campaign**
5. Watch real-time progress
6. Use **⏸️ Pause**, **▶️ Resume**, or **⏹️ Stop** to control

### 5.4 View Results

1. Go to **Logs** tab
2. View sent/failed emails
3. Click **📥 Export CSV** to download logs

---

## ⚠️ Important Notes

### Rate Limits

Microsoft Graph API has strict rate limits:
- **Personal accounts**: ~30 emails/minute, ~300/day
- **Business accounts**: Higher limits (varies by subscription)

The software automatically:
- Rotates accounts when limits are hit
- Retries failed emails
- Pauses when rate limited

### Best Practices

1. **Start Small**: Test with 5-10 emails first
2. **Add Delays**: Use 1-2 second delays to avoid rate limits
3. **Multiple Accounts**: Add multiple accounts for higher throughput
4. **Monitor Logs**: Check logs tab regularly for failures
5. **Valid Recipients**: Ensure email addresses are valid
6. **Compliance**: Only send to recipients who gave consent

### Token Management

- Tokens automatically refresh (expire after ~1 hour)
- No need to re-authenticate manually
- If token refresh fails, you'll be prompted to re-login

---

## 🐛 Troubleshooting

### Issue: "CLIENT_ID not found"
**Solution**: Ensure `.env` file exists with correct `CLIENT_ID`

### Issue: Authentication fails
**Solution**: 
- Check Azure app has correct permissions
- Ensure redirect URI is `http://localhost:8000/callback`
- Try different browser

### Issue: "No active accounts"
**Solution**: Add at least one account in Accounts tab

### Issue: "Rate limit exceeded"
**Solution**:
- Add more accounts
- Increase delay between emails
- Wait for rate limit to reset

### Issue: Emails not sending
**Solution**:
- Check account status in Accounts tab
- Verify HTML template is valid
- Check logs tab for error details
- Ensure internet connection is stable

---

## 📊 Features Summary

✅ **Implemented in Phase 1:**
- Background threading (non-blocking UI)
- Token auto-refresh
- Account rotation on rate limits
- Pause/Resume/Cancel controls
- Real-time progress tracking
- Tag system (#EMAIL#, #DATE#, etc.)
- HTML template support
- CSV/Excel recipient import
- Detailed logging with export
- Multi-account management
- Retry mechanism
- Database persistence

🚧 **Coming in Future Phases:**
- Attachment support (PDF, images)
- Inline base64 images
- Email preview
- Campaign save/load
- Template management
- Crash recovery
- Scheduler
- Secure credential storage
- Advanced validation

---

## 🆘 Support

For issues:
1. Check logs in `logs/` directory
2. Review send logs in Logs tab
3. Check database at `database/database.db`

---

## ⚖️ Legal Disclaimer

**Important**: This software is for legitimate bulk email sending only.

- ✅ Send to recipients who gave explicit consent
- ✅ Comply with CAN-SPAM Act, GDPR, and local laws
- ✅ Include unsubscribe links in emails
- ✅ Honor opt-out requests immediately
- ❌ Do not send spam or unsolicited emails
- ❌ Do not use for phishing or fraud
- ❌ Do not violate Microsoft Terms of Service

**You are responsible for how you use this software.**

---

## 📝 Next Steps

After successful setup:

1. **Test thoroughly** with a small batch
2. **Verify email delivery** (check spam folders)
3. **Monitor account health** in Dashboard
4. **Export logs regularly** for records
5. **Add multiple accounts** for higher volume
6. **Read Microsoft's sending limits** documentation

---

**Ready to send emails at scale! 🚀**
