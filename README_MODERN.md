# 📧 Outlook Bulk Mail Sender - Professional Edition

## 🚀 Quick Start

```bash
python run_modern.py
```

## ✨ Features Implemented

### 1. 📧 SMTP Accounts Management
- **Bulk Import**: Paste multiple SMTP accounts at once
- **Format**: `email|password|token|client_id`
- **Example**: `lxao5455@outlook.com|jnhg8221|token_here|9e5f94bc-e8a4-4e73-b8be-63364c29d753`
- **Test Function**: Test individual SMTP before sending
- **Real-time Status**: See active/failed accounts instantly

### 2. 📨 Recipients Management
- **Two Input Methods**:
  1. **CSV/Excel Upload**: Import from file (Email, Name format)
  2. **Copy & Paste**: Paste 500-5000 emails directly
- **Auto-Processing**: Handles large datasets (up to 5000 recipients)
- **Smart Removal**: Automatically removes sent emails from list
- **Real-time Counter**: Shows Total, Pending, Sent, and Remaining

### 3. 🚀 Smart Email Sending System

#### Delay Control
- Set delay between emails (1-60 seconds)
- Prevents rate limiting
- Customizable per campaign

#### Per SMTP Mode (Your Requirement)
Two options exactly as requested:

**Option 1: Auto Mode**
- SMTP sends maximum emails until error 400/401 occurs
- Automatically switches to next SMTP on error
- Reference: https://learn.microsoft.com/en-us/graph/errors

**Option 2: Limit Mode**
- Set custom limit (e.g., 5 emails per SMTP)
- Each SMTP sends exactly X emails then switches
- Example: Set to 5 → Each SMTP sends 5 emails only

#### Smart Data Management
- **5000 Data Upload**: Upload up to 5000 recipients at once
- **50 SMTP Upload**: Load 50 SMTP accounts simultaneously
- **Auto Calculation**: System calculates how many emails each SMTP can send
  - Example: 50 SMTP × 8 emails = 400 emails sent
  - Automatically removes those 400 from 5000 list
  - Remaining: 4600 emails
- **Continuous Process**: Upload new 50 SMTP → They send from remaining 4600
  - Next batch: 50 SMTP × 7 emails = 350 sent
  - New remaining: 4250 emails
- **Process Continues**: Until all 5000 emails are sent

### 4. 📊 Dashboard
- Real-time statistics
- Total SMTP accounts
- Total recipients
- Emails sent counter
- Success rate percentage
- Recent activity log

### 5. ⚙️ Settings
- Microsoft Client ID: `9e5f94bc-e8a4-4e73-b8be-63364c29d753`
- Configurable rate limits
- Request timeout settings
- Retry attempts configuration
- Email template customization

## 🎨 Modern Design Features

### Beautiful UI
- Modern gradient header
- Color-coded status indicators
- Responsive stat cards
- Professional color scheme
- Smooth animations

### User Experience
- Clear visual feedback
- Real-time progress bars
- Live activity log
- Error handling
- Confirmation dialogs

## 📋 How to Use

### Step 1: Add SMTP Accounts
1. Go to "📧 SMTP Accounts" tab
2. Click "📋 Add Bulk SMTP"
3. Paste your accounts (format: email|password|token|client_id)
4. System shows: Total, Active, Failed counts

### Step 2: Add Recipients
1. Go to "📨 Recipients" tab
2. Choose method:
   - Click "📁 Import CSV/Excel" to upload file
   - Click "📋 Copy & Paste" to paste emails
3. System shows: Total, Pending, Sent, Remaining

### Step 3: Configure Sending
1. Go to "🚀 Send Emails" tab
2. Set **Delay** (seconds between emails)
3. Choose **Per SMTP Mode**:
   - Auto: Sends until error 400/401
   - Limit: Set exact number per SMTP
4. Set **Daily Limit** per SMTP
5. Enable **Retry** if needed

### Step 4: Send Emails
1. Click "🚀 START SENDING"
2. Monitor progress in real-time
3. Use "⏸️ PAUSE" to pause
4. Use "⏹️ STOP" to stop completely
5. Watch live log for details

## 🔧 Technical Details

### Automatic SMTP Rotation
- System automatically rotates between SMTP accounts
- Detects errors 400/401 and switches
- In Limit mode: Switches after X emails
- Maximizes sending efficiency

### Data Management
- Recipients automatically removed after sending
- No duplicates sent
- Smart remaining count
- Continuous processing support

### Error Handling
- Automatic retry on failure
- Error logging
- SMTP status tracking
- Detailed error messages

## 📁 Project Structure

```
ui_modern/
├── __init__.py
├── main_window.py     # Main application window
├── accounts.py        # SMTP management
├── recipients.py      # Email data management
├── sender.py          # Sending control (YOUR REQUIREMENTS)
├── dashboard.py       # Statistics overview
└── settings.py        # Configuration

run_modern.py          # Launch script
```

## 🎯 Your Requirements - ALL IMPLEMENTED

✅ **SMTP Format**: email|password|token|client_id
✅ **Test Single SMTP**: Test button available
✅ **CSV/Excel Upload**: Full support with (Email, Name) format
✅ **Copy & Paste**: Box for pasting 500-1000+ emails
✅ **5000 Data Upload**: Supports up to 5000 recipients
✅ **50 SMTP Upload**: Supports 50+ SMTP accounts
✅ **Auto Calculation**: Mailer calculates max emails per batch
✅ **Auto Removal**: Removes sent emails from dataset
✅ **Continuous Process**: Upload new SMTP → Send from remaining data
✅ **Delay Option**: 1-60 seconds configurable
✅ **Per SMTP - Auto Mode**: Sends until error 400/401
✅ **Per SMTP - Limit Mode**: Set exact number (e.g., 5) per SMTP
✅ **Microsoft Graph Errors**: Handles error codes from Microsoft docs

## 🎨 Design Highlights

- 🎨 Modern gradient design
- 🌈 Color-coded status (Green=Success, Red=Failed, Yellow=Pending)
- 📊 Real-time statistics cards
- 📈 Progress bars with live updates
- 📋 Activity log with timestamps
- 🎯 Professional button styling
- ✨ Smooth hover effects
- 🔔 Clear notifications

## 💡 Tips

- Start with test mode to verify setup
- Use Auto mode for maximum efficiency
- Use Limit mode for precise control
- Monitor live log for real-time status
- Check Dashboard for overall statistics

## 🆘 Support

All features implemented as per your requirements. The UI is modern, professional, and fully functional!
