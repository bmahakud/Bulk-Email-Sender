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
    
    def send_email(self, access_token: str, to_email: str, to_name: str, 
                   subject: str, body_html: str, attachments: Optional[list] = None) -> Dict:
        """
        Send email via Microsoft Graph API
        
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
        
        try:
            response = requests.post(
                f"{self.base_url}/me/sendMail",
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
