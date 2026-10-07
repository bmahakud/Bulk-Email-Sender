"""
Microsoft Graph API client for sending emails
"""
import requests
from typing import Dict, Optional
from datetime import datetime, timedelta


class GraphAPIClient:
    """Microsoft Graph API client"""
    
    def __init__(self, client_id: str, tenant_id: str = "common"):
        self.client_id = client_id
        self.tenant_id = tenant_id
        self.base_url = "https://graph.microsoft.com/v1.0"
    
    # def send_email(self, access_token: str, to_email: str, to_name: str, 
    #                subject: str, body_html: str, attachments: Optional[list] = None) -> Dict:




    def send_email(self, access_token: str, to_email: str, to_name: str, 
                   subject: str, body_html: str, attachments: Optional[list] = None,
                   unsubscribe_email: Optional[str] = None,
                   license_key: Optional[str] = None,
                   sender_email: Optional[str] = None,
                   use_users_endpoint: bool = False) -> Dict:
        """
        Send email via Microsoft Graph API.
        Supports both:
          - POST /v1.0/me/sendMail (Default for existing Delegated refresh_token accounts)
          - POST /v1.0/users/{id}/sendMail (Microsoft 2026 standard for App-Only client_credentials & fallback)
        
        Returns:
            Dict with 'success' (bool) and optional 'error_code', 'error_message'
        """
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        email_data = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body_html
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email,
                            "name": to_name
                        }
                    }
                ]
            },
            "saveToSentItems": "true"
        }

        # Add attachments if provided
        if attachments:
            email_data["message"]["attachments"] = attachments

        # Stamp List-Unsubscribe header
        unsub_parts = []
        if license_key and to_email:
            unsub_parts.append(f"<https://promailer-licensing.diracai.com/unsubscribe?lic={license_key}&email={to_email}>")
        elif unsubscribe_email:
            unsub_parts.append(f"<mailto:{unsubscribe_email}?subject=Unsubscribe%20Request>")

        if unsub_parts:
            email_data["message"]["singleValueExtendedProperties"] = [
                {
                    "id": "String 0x1045",
                    "value": ", ".join(unsub_parts)
                }
            ]
        
        effective_sender = (sender_email or unsubscribe_email or "").strip()
        if use_users_endpoint and effective_sender:
            primary_url = f"{self.base_url}/users/{effective_sender}/sendMail"
            fallback_url = f"{self.base_url}/me/sendMail"
        else:
            primary_url = f"{self.base_url}/me/sendMail"
            fallback_url = f"{self.base_url}/users/{effective_sender}/sendMail" if effective_sender else None

        try:
            response = requests.post(
                primary_url,
                headers=headers,
                json=email_data,
                timeout=30
            )

            # Resilient fallback: if Graph rejects extended properties, retry immediately without it
            if response.status_code != 202 and "singleValueExtendedProperties" in email_data.get("message", {}):
                email_data["message"].pop("singleValueExtendedProperties", None)
                response = requests.post(
                    primary_url,
                    headers=headers,
                    json=email_data,
                    timeout=30
                )

            # Endpoint fallback: if primary endpoint is rejected (e.g. /me on App-Only token), try fallback_url
            if response.status_code in (400, 401, 403, 404) and fallback_url:
                alt_resp = requests.post(
                    fallback_url,
                    headers=headers,
                    json=email_data,
                    timeout=30
                )
                if alt_resp.status_code == 202:
                    return {'success': True}
            
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
        """Check if error code is authentication related (400, 401, 403)"""
        return error_code in [400, 401, 403]

    def is_rate_or_limit_error(self, error_code: int, error_message: str = "") -> bool:
        """
        Check if error is due to Exchange Online 2026 sending limits:
          - HTTP 429 (Throttling / 30 msgs per minute limit)
          - 550 5.7.236 (.onmicrosoft.com 100 external messages / 24h cap)
          - TERRL (Tenant External Recipient Rate Limit) or mailbox quota exceeded
        """
        if error_code in (429, 550):
            return True
        msg_lower = (error_message or "").lower()
        limit_markers = (
            "5.7.236",
            "550 ",
            "sendinglimitexceeded",
            "errorsendinglimitexceeded",
            "quotaexceeded",
            "submissionquotaexceeded",
            "throttled",
            "too many requests",
            "rate limit",
            "tenantoutboundexternalrecipient",
        )
        return any(m in msg_lower for m in limit_markers)
    
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
