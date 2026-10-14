"""
High Volume Email (HVE) & Exchange Online SMTP OAuth (XOAUTH2) Sender.
Compliant with Microsoft 365 2026 requirements:
- Endpoints: smtp.hve.mx.microsoft (HVE Bulk) / smtp.office365.com
- Auth: AUTH XOAUTH2 using OAuth 2.0 bearer token (scope: https://outlook.office365.com/.default)
- Synchronous SMTP delivery confirmation (detects MX rejections at gateway)
"""
import smtplib
import base64
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from typing import Dict, List, Optional
from loguru import logger


class HVESender:
    """High Volume Email & Exchange Online SMTP OAuth Sender"""

    HVE_ENDPOINT = "smtp.hve.mx.microsoft"
    STANDARD_ENDPOINT = "smtp.office365.com"
    PORT = 587

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
        password: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
        unsubscribe_email: Optional[str] = None,
        license_key: Optional[str] = None,
        preferred_host: Optional[str] = None,
        timeout: int = 35,
    ) -> Dict:
        """
        Sends an email using Microsoft High Volume Email (HVE) or Exchange Online SMTP
        via STARTTLS and AUTH XOAUTH2 (with standard password login fallback).

        Returns:
            Dict: {'success': bool, 'error_code': int, 'error_message': str, 'host': str}
        """
        # Determine endpoints to attempt: preferred -> HVE -> Standard Office 365
        candidate_hosts = []
        if preferred_host and preferred_host.strip():
            candidate_hosts.append(preferred_host.strip())
        if cls.HVE_ENDPOINT not in candidate_hosts:
            candidate_hosts.append(cls.HVE_ENDPOINT)
        if cls.STANDARD_ENDPOINT not in candidate_hosts:
            candidate_hosts.append(cls.STANDARD_ENDPOINT)

        # Build RFC-compliant MIME message
        msg = cls._build_mime_message(
            sender_email=sender_email,
            sender_name=sender_name,
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            body_html=body_html,
            attachments=attachments,
            unsubscribe_email=unsubscribe_email,
            license_key=license_key,
        )

        last_error = None
        last_code = 500

        for host in candidate_hosts:
            try:
                server = smtplib.SMTP(host, cls.PORT, timeout=timeout)
                server.ehlo()
                server.starttls()
                server.ehlo()

                authed = False
                # 1. Try XOAUTH2 first if access_token is present
                if access_token:
                    xoauth_payload = f"user={sender_email}\x01auth=Bearer {access_token}\x01\x01"
                    xoauth_b64 = base64.b64encode(xoauth_payload.encode("utf-8")).decode("ascii")

                    code, resp = server.docmd("AUTH", "XOAUTH2 " + xoauth_b64)
                    if code in (235, 250):
                        authed = True
                    elif code == 334:
                        try:
                            err_raw = base64.b64decode(resp).decode("utf-8", errors="ignore")
                        except Exception:
                            err_raw = str(resp)
                        code2, resp2 = server.docmd("")
                        if code2 in (235, 250):
                            authed = True
                        else:
                            last_code = code2
                            resp2_str = resp2.decode("utf-8", errors="ignore") if isinstance(resp2, bytes) else str(resp2)
                            last_error = f"XOAUTH2 rejected on {host} ({code2} {resp2_str} | Challenge: {err_raw})"
                    else:
                        last_code = code
                        resp_str = resp.decode("utf-8", errors="ignore") if isinstance(resp, bytes) else str(resp)
                        last_error = f"XOAUTH2 failed on {host} ({code} {resp_str})"

                # 2. Try password login fallback (for HVE accounts created with dedicated passwords)
                if not authed and password and password.strip() and password.strip() != "dummy_password":
                    try:
                        server.login(sender_email, password.strip())
                        authed = True
                    except Exception as pe:
                        last_error = f"Login failed on {host}: {pe}"

                if not authed:
                    server.quit()
                    last_code = 535
                    if not last_error:
                        last_error = f"Authentication failed on {host} (XOAUTH2 / Password rejected)"
                    continue

                # Synchronous SMTP transmission
                server.send_message(msg, from_addr=sender_email, to_addrs=[to_email])
                server.quit()

                return {
                    "success": True,
                    "host": host,
                    "message": "Delivered successfully via High Volume Email SMTP",
                }

            except smtplib.SMTPAuthenticationError as e:
                last_code = e.smtp_code
                last_error = f"Authentication Error on {host} ({e.smtp_code}): {e.smtp_error.decode() if isinstance(e.smtp_error, bytes) else e.smtp_error}"
                continue
            except smtplib.SMTPRecipientsRefused as e:
                # Recipient rejected by ISP / Exchange
                ref_err = str(e)
                return {
                    "success": False,
                    "error_code": 550,
                    "error_message": f"Recipient Refused: {ref_err}",
                    "is_recipient_error": True,
                    "host": host,
                }
            except smtplib.SMTPSenderRefused as e:
                return {
                    "success": False,
                    "error_code": e.smtp_code,
                    "error_message": f"Sender Refused on {host} ({e.smtp_code}): {e.smtp_error.decode() if isinstance(e.smtp_error, bytes) else e.smtp_error}",
                    "host": host,
                }
            except smtplib.SMTPResponseException as e:
                last_code = e.smtp_code
                last_error = f"SMTP Error on {host} ({e.smtp_code}): {e.smtp_error.decode() if isinstance(e.smtp_error, bytes) else e.smtp_error}"
                continue
            except Exception as e:
                last_error = f"Connection error on {host}: {str(e)}"
                continue

        return {
            "success": False,
            "error_code": last_code,
            "error_message": last_error or "All SMTP endpoints failed",
            "host": candidate_hosts[0] if candidate_hosts else "unknown",
        }

    @classmethod
    def _build_mime_message(
        cls,
        sender_email: str,
        sender_name: str,
        to_email: str,
        to_name: str,
        subject: str,
        body_html: str,
        attachments: Optional[List[Dict]] = None,
        unsubscribe_email: Optional[str] = None,
        license_key: Optional[str] = None,
    ) -> MIMEMultipart:
        """
        Builds a standards-compliant MIME multipart message.
        Structure:
          multipart/mixed
            └── multipart/alternative
                  ├── text/plain
                  └── multipart/related
                        ├── text/html
                        └── inline images (cid)
            └── file attachments (PDF / Image)
        """
        # Outer message
        msg = MIMEMultipart("mixed")
        sender_display = f"{sender_name} <{sender_email}>" if sender_name else sender_email
        recipient_display = f"{to_name} <{to_email}>" if to_name else to_email

        msg["From"] = sender_display
        msg["To"] = recipient_display
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate(localtime=True)
        domain = sender_email.split("@")[1] if "@" in sender_email else "contoso.com"
        msg["Message-ID"] = email.utils.make_msgid(domain=domain)

        # List-Unsubscribe headers
        unsub_parts = []
        if license_key and to_email:
            unsub_parts.append(f"<https://promailer-licensing.diracai.com/unsubscribe?lic={license_key}&email={to_email}>")
        if unsubscribe_email:
            unsub_parts.append(f"<mailto:{unsubscribe_email}?subject=Unsubscribe%20Request>")
        if unsub_parts:
            msg["List-Unsubscribe"] = ", ".join(unsub_parts)
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        # Alternative container (Plain text + HTML)
        alt_part = MIMEMultipart("alternative")

        # Plain text version (strips html tags for fallback)
        import re
        clean_text = re.sub(r"<[^>]+>", " ", body_html)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        part_text = MIMEText(clean_text or subject, "plain", "utf-8")
        alt_part.attach(part_text)

        # Related container for HTML + Inline images (CIDs)
        related_part = MIMEMultipart("related")
        part_html = MIMEText(body_html, "html", "utf-8")
        related_part.attach(part_html)

        # Process attachments (inline vs regular)
        if attachments:
            for att in attachments:
                raw_b64 = att.get("contentBytes", "")
                if not raw_b64:
                    continue
                try:
                    file_bytes = base64.b64decode(raw_b64)
                except Exception:
                    continue

                att_name = att.get("name", "attachment")
                content_type = att.get("contentType", "application/octet-stream")
                is_inline = bool(att.get("isInline", False))
                cid = att.get("contentId")

                maintype, subtype = content_type.split("/", 1) if "/" in content_type else ("application", "octet-stream")

                if is_inline and cid:
                    # Inline image
                    img_mime = MIMEImage(file_bytes, _subtype=subtype)
                    clean_cid = cid.strip("<>")
                    img_mime.add_header("Content-ID", f"<{clean_cid}>")
                    img_mime.add_header("Content-Disposition", "inline", filename=att_name)
                    related_part.attach(img_mime)
                else:
                    # Regular attachment (PDF / Image)
                    if maintype == "application" and subtype == "pdf":
                        file_mime = MIMEApplication(file_bytes, _subtype="pdf")
                    elif maintype == "image":
                        file_mime = MIMEImage(file_bytes, _subtype=subtype)
                    else:
                        file_mime = MIMEBase(maintype, subtype)
                        file_mime.set_payload(file_bytes)
                        email.encoders.encode_base64(file_mime)

                    file_mime.add_header("Content-Disposition", "attachment", filename=att_name)
                    msg.attach(file_mime)

        alt_part.attach(related_part)
        msg.attach(alt_part)

        return msg

