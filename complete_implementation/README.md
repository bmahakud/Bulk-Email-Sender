# Outlook Bulk Mail Sender

Professional bulk email sender using Microsoft Graph API with account rotation, HTML templates, and tag system.

## Features

- 📧 Bulk email sending via Microsoft Graph API
- 🔄 Automatic account rotation on rate limits
- 🏷️ Dynamic tag system (#EMAIL#, #DATE#, etc.)
- 📎 Multiple attachment types (PDF, images, HTML)
- 🖼️ Inline base64 image support
- 📊 Real-time progress tracking
- 💾 SQLite database for queue management
- 🔐 Secure OAuth2 authentication via MSAL

## Tech Stack

- **UI**: PySide6 (Qt)
- **Language**: Python 3.12+
- **Database**: SQLite
- **Auth**: MSAL (Microsoft Authentication Library)
- **Email Service**: Microsoft Graph API

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python app.py
```

## Important Notes

⚠️ **Legal Compliance**: Ensure you have explicit consent from recipients and comply with anti-spam regulations (CAN-SPAM Act, GDPR).

⚠️ **Rate Limits**: Microsoft Graph API has sending limits. The software handles rotation automatically.

## License

Proprietary
