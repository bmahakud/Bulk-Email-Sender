"""
Microsoft Graph API client for sending emails
"""
import requests
import base64
import email.utils
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Optional
from datetime import datetime, timedelta


class GraphAPIClient:
    """Microsoft Graph API client"""
    
    def __init__(self, client_id: str, tenant_id: str = "common"):
        self.client_id = client_id
        self.tenant_id = tenant_id
        self.base_url = "https://graph.microsoft.com/v1.0"
    
    def send_email(self, access_token: str, to_email: str, to_name: str, 
                   subject: str, body_html: str, attachments: Optional[list] = None,
                   unsubscribe_email: Optional[str] = None,
                   license_key: Optional[str] = None,
                   sender_email: Optional[str] = None) -> Dict:
        """
        Send email via Microsoft Graph API with RFC 8058 List-Unsubscribe support.
        
        Uses raw MIME encoding to ensure List-Unsubscribe and List-Unsubscribe-Post
        headers are natively preserved and signed by Microsoft Exchange Online.
        Falls back seamlessly to JSON format if raw MIME is rejected.
        
        Returns:
            Dict with 'success' (bool) and optional 'error_code', 'error_message'
        """
        target_url = f"{self.base_url}/users/{sender_email}/sendMail" if sender_email else f"{self.base_url}/me/sendMail"
        
        # ── 1. Prepare Unsubscribe URIs (RFC 8058 compliant: https + mailto) ──
        import urllib.parse
        unsub_parts = []
        encoded_to = urllib.parse.quote(to_email) if to_email else ""
        encoded_lic = urllib.parse.quote(license_key or "Pooja")
        if to_email:
            unsub_parts.append(f"<https://promailer-licensing.diracai.com/unsubscribe?lic={encoded_lic}&email={encoded_to}>")
        
        target_unsub_email = unsubscribe_email or sender_email or "unsubscribe@diracai.com"
        if target_unsub_email and to_email:
            unsub_parts.append(f"<mailto:{target_unsub_email}?subject=Unsubscribe%20{to_email}>")
        elif target_unsub_email:
            unsub_parts.append(f"<mailto:{target_unsub_email}?subject=Unsubscribe%20Request>")

        # ── 2. Primary Delivery Engine: Raw RFC 822 MIME via Graph ──
        # Sending raw MIME bypasses Graph's JSON header restrictions and guarantees
        # that List-Unsubscribe & List-Unsubscribe-Post are preserved and DKIM signed!
        try:
            mime_msg = MIMEMultipart("mixed")
            snd_display = sender_email or ""
            mime_msg["From"] = email.utils.formataddr((snd_display, sender_email)) if sender_email else snd_display
            mime_msg["To"] = email.utils.formataddr((to_name or "", to_email))
            mime_msg["Subject"] = subject
            mime_msg["Date"] = email.utils.formatdate(localtime=True)
            domain = sender_email.split("@")[-1] if (sender_email and "@" in sender_email) else "outlook.com"
            mime_msg["Message-ID"] = email.utils.make_msgid(domain=domain)
            mime_msg["X-Mailer"] = "Microsoft Outlook 16.0"
            mime_msg["X-MimeOLE"] = "Produced By Microsoft Exchange V16.0"
            mime_msg["X-MS-Has-Attach"] = "yes" if attachments else "no"
            mime_msg["Thread-Topic"] = subject
            mime_msg["Thread-Index"] = base64.b64encode(os.urandom(22)).decode("ascii")

            if unsub_parts:
                mime_msg["List-Unsubscribe"] = ", ".join(unsub_parts)
                mime_msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
                mime_msg["List-ID"] = f"<bulletin.{domain}>"
                mime_msg["List-Help"] = f"<mailto:{target_unsub_email}?subject=Help>"
                mime_msg["Precedence"] = "bulk"

            inline_atts = [att for att in (attachments or []) if att.get("isInline")]
            regular_atts = [att for att in (attachments or []) if not att.get("isInline")]

            alt_part = MIMEMultipart("alternative")
            html_part = MIMEText(body_html, "html", "utf-8")
            alt_part.attach(html_part)

            if inline_atts:
                rel_part = MIMEMultipart("related")
                rel_part.attach(alt_part)
                for att in inline_atts:
                    try:
                        c_bytes = base64.b64decode(att.get("contentBytes", ""))
                        cid = att.get("contentId", "").strip("<>")
                        img_part = MIMEImage(c_bytes)
                        img_part.add_header("Content-ID", f"<{cid}>")
                        img_part.add_header("Content-Disposition", "inline", filename=att.get("name", "inline.png"))
                        rel_part.attach(img_part)
                    except Exception:
                        pass
                mime_msg.attach(rel_part)
            else:
                mime_msg.attach(alt_part)

            if regular_atts:
                for att in regular_atts:
                    try:
                        att_name = att.get("name", "attachment")
                        content_type = att.get("contentType", "application/octet-stream")
                        c_bytes = base64.b64decode(att.get("contentBytes", ""))
                        if "/" in content_type:
                            main_type, sub_type = content_type.split("/", 1)
                        else:
                            main_type, sub_type = "application", "octet-stream"
                        if main_type == "image":
                            p = MIMEImage(c_bytes, _subtype=sub_type)
                        elif main_type == "application" and sub_type == "pdf":
                            p = MIMEApplication(c_bytes, _subtype="pdf")
                        else:
                            p = MIMEBase(main_type, sub_type)
                            p.set_payload(c_bytes)
                            encoders.encode_base64(p)
                        p.add_header("Content-Disposition", "attachment", filename=att_name)
                        mime_msg.attach(p)
                    except Exception:
                        pass

            raw_b64 = base64.b64encode(mime_msg.as_bytes()).decode("ascii")
            mime_headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'text/plain'
            }

            resp = requests.post(target_url, headers=mime_headers, data=raw_b64, timeout=30)
            if resp.status_code == 202:
                return {'success': True}
            
            # Auto-switch /users/{sender} <-> /me if permission differs
            alt_url = None
            if "/users/" in target_url:
                alt_url = f"{self.base_url}/me/sendMail"
            elif target_url.endswith("/me/sendMail") and sender_email:
                alt_url = f"{self.base_url}/users/{sender_email}/sendMail"
            if alt_url:
                alt_resp = requests.post(alt_url, headers=mime_headers, data=raw_b64, timeout=30)
                if alt_resp.status_code == 202:
                    return {'success': True}
        except Exception:
            pass

        # ── 3. Fallback Delivery Engine: Standard JSON Payload ──
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        recipient_info = {"address": to_email}
        if to_name and to_name.strip() and to_name.strip() != to_email:
            recipient_info["name"] = to_name.strip()

        email_data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body_html
                },
                "toRecipients": [
                    {
                        "emailAddress": recipient_info
                    }
                ]
            },
            "saveToSentItems": True
        }

        if attachments:
            email_data["message"]["attachments"] = attachments

        if unsub_parts:
            unsub_val = ", ".join(unsub_parts)
            email_data["message"]["singleValueExtendedProperties"] = [
                {
                    "id": "String 0x1045",
                    "value": unsub_val
                },
                {
                    "id": "String {00020386-0000-0000-C000-000000000046} Name List-Unsubscribe",
                    "value": unsub_val
                },
                {
                    "id": "String {00020386-0000-0000-C000-000000000046} Name List-Unsubscribe-Post",
                    "value": "List-Unsubscribe=One-Click"
                },
                {
                    "id": "String {00020386-0000-0000-C000-000000000046} Name List-ID",
                    "value": f"<bulletin.{domain}>"
                },
                {
                    "id": "String {00020386-0000-0000-C000-000000000046} Name Precedence",
                    "value": "bulk"
                }
            ]
        
        try:
            response = requests.post(
                target_url,
                headers=headers,
                json=email_data,
                timeout=30
            )

            if response.status_code != 202:
                alt_url = None
                if "/users/" in target_url:
                    alt_url = f"{self.base_url}/me/sendMail"
                elif target_url.endswith("/me/sendMail") and sender_email:
                    alt_url = f"{self.base_url}/users/{sender_email}/sendMail"
                
                if alt_url:
                    alt_response = requests.post(
                        alt_url,
                        headers=headers,
                        json=email_data,
                        timeout=30
                    )
                    if alt_response.status_code == 202:
                        response = alt_response
                        target_url = alt_url

            if response.status_code != 202 and "singleValueExtendedProperties" in email_data.get("message", {}):
                email_data["message"].pop("singleValueExtendedProperties", None)
                response = requests.post(
                    target_url,
                    headers=headers,
                    json=email_data,
                    timeout=30
                )
            
            if response.status_code == 202:
                return {'success': True}
            else:
                try:
                    error_data = response.json()
                except Exception:
                    error_data = {}
                error_code = response.status_code
                error_message = error_data.get('error', {}).get('message', response.text or 'Unknown error')
                
                return {
                    'success': False,
                    'error_code': error_code,
                    'error_message': error_message
                }
        
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error_code': 408,
                'error_message': 'Request timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'error_code': 500,
                'error_message': str(e)
            }
    
    def is_auth_error(self, error_code: int) -> bool:
        """Check if error code is authentication related (400, 401)"""
        return error_code in [400, 401, 403]
    
    def get_user_info(self, access_token: str) -> Optional[Dict]:
        """Get user profile information"""
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/me",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except Exception:
            return None
