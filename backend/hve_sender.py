"""
High Volume Email (HVE) & Exchange Online SMTP OAuth (XOAUTH2) Sender.
Compliant with Microsoft 365 requirements:
  - Endpoints: smtp.office365.com:587 / smtp.hve.mx.microsoft:587
  - Auth: AUTH XOAUTH2 using OAuth 2.0 bearer token
    * App-Only scope: https://outlook.office365.com/.default (SMTP.SendAsApp)
    * Delegated scope: https://outlook.office.com/SMTP.Send (SMTP.Send)
  - Native MAPI & Exchange headers: X-Mailer, X-MimeOLE, Thread-Topic, Thread-Index, X-MS-Has-Attach
"""
import os
import smtplib
import base64
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from typing import Dict, List, Optional
import msal
from loguru import logger


class HVESender:
    """High Volume Email & Exchange Online SMTP OAuth Sender with MAPI Headers"""

    PRIMARY_ENDPOINT = "smtp.office365.com"
    HVE_ENDPOINT = "smtp.hve.mx.microsoft"
    OUTLOOK_ENDPOINT = "smtp-mail.outlook.com"
    PORT = 587

    @classmethod
    def get_access_token(cls, tenant_id: str, client_id: str, client_secret: str) -> Optional[str]:
        """
        Acquire OAuth2 token using app-only client_credentials flow.
        Scope: https://outlook.office365.com/.default (Exchange Online SMTP.SendAsApp)
        """
        try:
            app = msal.ConfidentialClientApplication(
                client_id=client_id,
                authority=f"https://login.microsoftonline.com/{tenant_id}",
                client_credential=client_secret
            )
            result = app.acquire_token_for_client(
                scopes=["https://outlook.office365.com/.default"]
            )
            if "access_token" in result:
                return result["access_token"]
            logger.error(f"Failed to acquire HVE token: {result.get('error_description') or result.get('error')}")
            return None
        except Exception as e:
            logger.error(f"Error acquiring HVE token: {e}")
            return None

    @classmethod
    def get_delegated_smtp_token(cls, client_id: str, refresh_token: str) -> Optional[str]:
        """
        Acquire OAuth2 token using delegated refresh token flow for SMTP.
        Scope: https://outlook.office.com/SMTP.Send (Exchange Online delegated SMTP)
        """
        try:
            app = msal.PublicClientApplication(
                client_id=client_id,
                authority="https://login.microsoftonline.com/common"
            )
            result = app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=["https://outlook.office.com/SMTP.Send"]
            )
            if "access_token" in result:
                return result["access_token"]
            
            # Fallback to standard refresh
            result_fb = app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=["User.Read", "Mail.Send"]
            )
            if "access_token" in result_fb:
                return result_fb["access_token"]
                
            logger.error(f"Failed to acquire delegated SMTP token: {result.get('error_description') or result.get('error')}")
            return None
        except Exception as e:
            logger.error(f"Error acquiring delegated SMTP token: {e}")
            return None

    @classmethod
    def send_email(
        cls,
        sender_email: str,
        sender_name: str,
        to_email: str,
        to_name: str,
        subject: str,
        body_html: str,
        access_token: str,
        attachments: Optional[List[Dict]] = None,
        unsubscribe_email: Optional[str] = None,
        license_key: Optional[str] = None,
        preferred_host: Optional[str] = None,
        timeout: int = 30,
    ) -> Dict:
        """
        Send an email using Exchange Online SMTP via AUTH XOAUTH2 with MAPI headers.
        """
        # Build MIME Message
        msg = MIMEMultipart("mixed")
        msg["From"] = email.utils.formataddr((sender_name or "", sender_email))
        msg["To"] = email.utils.formataddr((to_name or "", to_email))
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate(localtime=True)
        
        domain = sender_email.split("@")[-1] if "@" in sender_email else "outlook.com"
        msg["Message-ID"] = email.utils.make_msgid(domain=domain)

        # ── Stamp MAPI & Exchange Transport Headers ──
        # These headers ensure the email is identified as Microsoft Exchange / Outlook MAPI
        msg["X-Mailer"] = "Microsoft Outlook 16.0"
        msg["X-MimeOLE"] = "Produced By Microsoft Exchange V16.0"
        msg["X-MS-Has-Attach"] = "yes" if attachments else "no"
        msg["Thread-Topic"] = subject
        msg["Thread-Index"] = base64.b64encode(os.urandom(22)).decode("ascii")

        # ── List-Unsubscribe Headers ──
        unsub_parts = []
        if license_key and to_email:
            unsub_parts.append(f"<https://promailer-licensing.diracai.com/unsubscribe?lic={license_key}&email={to_email}>")
        if unsubscribe_email:
            unsub_parts.append(f"<mailto:{unsubscribe_email}?subject=Unsubscribe%20Request>")
        if unsub_parts:
            msg["List-Unsubscribe"] = ", ".join(unsub_parts)
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        # Body: multipart/alternative (plain-text fallback + HTML)
        alt_part = MIMEMultipart("alternative")
        html_part = MIMEText(body_html, "html", "utf-8")
        alt_part.attach(html_part)
        msg.attach(alt_part)

        # Process attachments (handles Graph format: name, contentType, contentBytes)
        if attachments:
            for att in attachments:
                try:
                    att_name = att.get("name", "attachment")
                    content_bytes_b64 = att.get("contentBytes", "")
                    content_type = att.get("contentType", "application/octet-stream")
                    raw_data = base64.b64decode(content_bytes_b64)

                    if "/" in content_type:
                        main_type, sub_type = content_type.split("/", 1)
                    else:
                        main_type, sub_type = "application", "octet-stream"

                    if main_type == "image":
                        part = MIMEImage(raw_data, _subtype=sub_type)
                    elif main_type == "application" and sub_type == "pdf":
                        part = MIMEApplication(raw_data, _subtype="pdf")
                    else:
                        part = MIMEBase(main_type, sub_type)
                        part.set_payload(raw_data)
                        from email import encoders
                        encoders.encode_base64(part)

                    part.add_header("Content-Disposition", f'attachment; filename="{att_name}"')
                    msg.attach(part)
                except Exception as att_err:
                    logger.warning(f"Failed to attach file to HVE message: {att_err}")

        # XOAUTH2 string format: user=<user>\x01auth=Bearer <token>\x01\x01
        xoauth_str = f"user={sender_email}\x01auth=Bearer {access_token}\x01\x01"
        xoauth_b64 = base64.b64encode(xoauth_str.encode("utf-8")).decode("ascii")

        hosts_to_try = [preferred_host] if preferred_host else [cls.PRIMARY_ENDPOINT, cls.HVE_ENDPOINT, cls.OUTLOOK_ENDPOINT]

        last_error = "Unknown error"
        last_code = 0

        for host in hosts_to_try:
            try:
                server = smtplib.SMTP(host, cls.PORT, timeout=timeout)
                server.ehlo()
                server.starttls()
                server.ehlo()

                # Perform AUTH XOAUTH2
                auth_code, auth_resp = server.docmd("AUTH", "XOAUTH2 " + xoauth_b64)

                if auth_code == 334:
                    # Challenge response: send empty line
                    auth_code, auth_resp = server.docmd("")

                if auth_code != 235:
                    err_msg = auth_resp.decode("utf-8", errors="ignore") if isinstance(auth_resp, bytes) else str(auth_resp)
                    server.quit()
                    last_code = auth_code
                    last_error = f"SMTP AUTH Failed on {host} ({auth_code}): {err_msg}"
                    continue

                # Send message
                server.send_message(msg)
                server.quit()
                return {"success": True, "host": host}

            except smtplib.SMTPResponseException as e:
                last_code = e.smtp_code
                last_error = f"SMTP Error ({e.smtp_code}): {e.smtp_error.decode('utf-8', errors='ignore') if isinstance(e.smtp_error, bytes) else str(e.smtp_error)}"
            except Exception as e:
                last_error = f"SMTP Connection error on {host}: {e}"

        return {"success": False, "error_code": last_code, "error_message": last_error}
