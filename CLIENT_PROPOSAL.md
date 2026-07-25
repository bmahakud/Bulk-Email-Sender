# 📧 ProMailer Pro — Bulk Email Campaign Software
### Client Proposal | Feature List | Technology & Delivery Timeline

---

## 🧾 Project Overview

**ProMailer Pro** is a professional-grade desktop bulk email campaign management system built for
high-volume email marketing operations. It connects via Microsoft's Graph API to send emails
through Outlook/Microsoft 365 accounts, with full automation, multi-campaign tasking, intelligent
SMTP rotation, and dynamic content personalization.

---

## ✅ Complete Feature List

### 1. 📊 Live Analytics Dashboard
- Real-time global statistics: Total SMTP accounts, Total Recipients, Emails Sent, Success Rate
- Recent activity log with timestamps across all running campaigns
- Auto-refreshing stats (every 2 seconds)
- Aggregated sent/failed/queue counts across all active tasks

---

### 2. 📧 SMTP Account Management
| Feature | Details |
|--------|---------|
| Bulk SMTP Paste | Paste hundreds of accounts at once in `email\|password\|token\|client_id` format |
| CSV File Import | Import multiple CSV files simultaneously |
| SMTP Testing | Test individual SMTP accounts for validity |
| Remove / Clear | Remove selected or clear all accounts |
| Status Tracking | Per-account status (Active / Failed / Exhausted) |
| Auto SMTP Rotation | Automatically switches to next SMTP on error or after send limit |
| 50+ SMTP Support | Handles large SMTP pools efficiently |

---

### 3. 📨 Recipient Management
| Feature | Details |
|--------|---------|
| CSV / Excel Import | Import multiple `.csv` or `.xlsx` files at once |
| Bulk Copy & Paste | Paste thousands of emails directly into the app |
| 5,000+ Recipients Support | Handles large recipient lists smoothly |
| Status Tracking | Per-recipient status: Pending / Sent / Failed |
| Auto Data Removal | Sent recipients automatically removed from queue |
| Stats Cards | Total, Pending, Sent, Remaining counts |

---

### 4. 📝 Advanced Template System (5 Sub-tabs)

#### A. Body Content
- **Plain Text** email body with full tag support
- **HTML Body** with automatic inline Base64 image conversion (no broken images)
- **HTML → Image** mode: renders HTML as an image inside the email body
- **HTML → PDF (body)** mode: sends HTML as a PDF attachment + plain text body
- **HTML → Image (body)** mode: sends HTML as an image attachment + plain text body

#### B. Attachments (Base64 Encoded)
- Upload multiple **Image** attachments (GIF, PNG, JPEG, JPG, WEBP)
- Upload multiple **PDF** attachments
- **Personalized naming**: each attachment is named using the recipient's email prefix + random 4-digit code
  - Example: `groupleeman4829.pdf`
- Full Base64 encoding for maximum deliverability

#### C. Subject Lines
- Add multiple subject lines (one-by-one or bulk paste)
- **Auto-rotation** — each email gets the next subject in sequence
- Full tag support within subjects

#### D. Sender Names
- Default mode: uses SMTP email as sender name
- Custom mode: upload multiple sender names with **auto-rotation**
- Bulk paste (one name per line)

#### E. Custom Tags (Dynamic Personalization)
| Tag | Description |
|-----|-------------|
| `#NAME#` | Recipient name from CSV (or email prefix) |
| `#EMAIL#` | Recipient email address |
| `#TFN1#` | Phone / Tax File Number 1 |
| `#TFN2#` | Phone / Tax File Number 2 |
| `#DATE#` | Auto system date (e.g. July 6, 2026) |
| `#TIME#` | System time |
| `#INVOICE#` | Random invoice ID (e.g. INV-26GFY-6366) |
| `#ORDERID#` | Random order ID (e.g. 8266367-2026) |
| `#TXNID#` | Random 9-character transaction ID |
| `#TYPE#` | Random payment type (Bank Transfer, PayPal, ACH…) |
| `#AMOUNT#` | Custom or random amount in range |
| `#KEY#` | Random UUID key |
| `#GUID#` | Random GUID |
| `#SNUMBER#` | Random 6-digit serial number |
| `#ADDRESS#` | Cycles through uploaded address list |

---

### 5. 🚀 Multi-Task Campaign Engine
| Feature | Details |
|--------|---------|
| Dynamic Task Creation | Create unlimited campaign tasks on-demand |
| Per-Task Controls | Individual START / PAUSE / STOP per task |
| Global Controls | Start All / Pause All / Stop All with one click |
| Task Tabs | Each task runs in its own dedicated tab panel |
| Task Removal | Close/delete any task at any time |

---

### 6. ⚙️ SMTP Send Modes
| Mode | Behavior |
|------|----------|
| **Auto Mode** | Sends until HTTP 400/401 auth error, then auto-switches to next SMTP |
| **Limit Mode** | Each SMTP sends exactly `N` emails before rotating to the next |
| Error Detection | Detects 400, 401, 403 auth errors, marks SMTP as failed |
| Daily Limit | Configurable daily send limit per SMTP account |
| Retry Logic | Configurable retry attempts on soft failures |

---

### 7. 🔄 Rotation Logic
- Multiple **HTML templates** — rotates per email (A/B testing)
- Multiple **subject lines** — rotates per email
- Multiple **sender names** — rotates per email
- Multiple **SMTP accounts** — rotates on error or after send limit

---

### 8. 💾 Persistent Settings & Database
- SQLite database stores all SMTP accounts, recipients, and send logs
- Settings (TFN, templates, subjects, sender names) persist across sessions
- Only clear SMTP + Recipients between campaigns — all other settings stay!
- Full campaign history and send logs stored for reference

---

### 9. 📋 Real-Time Send Panel (Per Task)
- Delay control between emails (1–60 seconds)
- Live progress bar (percentage complete)
- Live stats: Sent / Failed / Remaining / Current SMTP
- Full activity log with timestamps
- START / PAUSE / STOP buttons

---

### 10. ⚙️ Settings Panel
- Microsoft Client ID & Tenant ID configuration
- Rate limit settings
- Request timeout configuration
- Max retry attempts

---

### 11. 🏷 Tag Reference Popup
- One-click access to complete tag reference from the toolbar
- Lists all supported tags with descriptions

---

## 🛠 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **UI Framework** | PySide6 (Qt for Python 6) | Professional desktop application |
| **Email API** | Microsoft Graph API | Sends emails via Outlook/Microsoft 365 |
| **Authentication** | MSAL (Microsoft Authentication Library) | OAuth2 token management |
| **Database** | SQLite (built-in) | Local persistent data storage |
| **HTML Processing** | BeautifulSoup4 | HTML parsing and inline image conversion |
| **HTML Rendering** | Custom HTMLRenderer | HTML → PDF / HTML → Image conversion |
| **CSV/Excel** | pandas + openpyxl | Import recipient lists |
| **Image Processing** | Pillow (PIL) | Image encoding and conversion |
| **Template Engine** | Jinja2 | Dynamic content rendering |
| **Logging** | loguru | Structured application logging |
| **HTTP Client** | requests | API communication |
| **Language** | Python 3.10+ | Core application language |
| **Platform** | Windows / Linux / macOS | Cross-platform desktop app |

---

## 🗓 Delivery Timeline

| Phase | Task | Duration | Status |
|-------|------|----------|--------|
| **Phase 1** | UI Design & All Tabs (Dashboard, SMTP, Recipients, Templates, Send, Settings) | **Completed** | ✅ Done |
| **Phase 2** | Backend Engine (Graph API, SMTP Rotation, Template Manager, Database) | **Completed** | ✅ Done |
| **Phase 3** | Multi-Task Campaign Engine (Dynamic Tasks, Global Controls, Dashboard) | **Completed** | ✅ Done |
| **Phase 4** | Advanced Body Modes (HTML→Image, HTML→PDF, Base64 attachments) | **Completed** | ✅ Done |
| **Phase 5** | Advanced Tags System (Invoice, GUID, Amount, Address, etc.) | **Completed** | ✅ Done |
| **Phase 6** | Persistent Campaign Settings (DB save/load for all parameters) | **Completed** | ✅ Done |
| **Phase 7** | Final Integration Testing & Bug Fixes | **~3 hours** | 🔧 In Progress |
| **Phase 8** | Packaging / Delivery (EXE or final handover) | **1–2 days** | 📦 Planned |

> **Estimated Final Delivery: 1–2 business days** from current date (July 6, 2026)

---

## 📌 Summary

| Category | Details |
|----------|---------|
| **Application Type** | Desktop Software (Windows/Linux/macOS) |
| **Email Provider** | Microsoft Outlook / Microsoft 365 (Graph API) |
| **Max SMTP Accounts** | Unlimited (50+ tested) |
| **Max Recipients** | Unlimited (5,000+ tested) |
| **Campaigns** | Unlimited simultaneous tasks |
| **Body Formats** | Plain Text, HTML, HTML→Image, HTML→PDF, HTML→Image Attachment |
| **Attachment Types** | PDF, PNG, JPG, GIF, WEBP (all Base64 encoded) |
| **Personalization Tags** | 15+ dynamic tags |
| **Data Persistence** | SQLite — survives app restarts |
| **Deployment** | Standalone Python app (packageable as EXE) |

---

*ProMailer Pro — Professional Bulk Email Campaign Management System*
*Prepared: July 6, 2026*
