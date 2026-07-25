"""
Microsoft Graph API client
"""
import requests
from typing import Optional, Dict, List
from loguru import logger


class GraphClient:
    """Microsoft Graph API client for sending emails"""
    
    BASE_URL = "https://graph.microsoft.com/v1.0"
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def send_email(self, to_email: str, subject: str, body_html: str, 
                   attachments: Optional[List[Dict]] = None) -> Dict:
        """
        Send email via Microsoft Graph API
        
        Args:
            to_email: Recipient email
            subject: Email subject
            body_html: HTML body content
            attachments: List of attachments with base64 content
            
        Returns:
            Dict with status, message, and response_code
        """
        try:
            # Build email message
            message = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": body_html
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": to_email
                            }
                        }
                    ]
                }
            }
            
            # Add attachments if provided
            if attachments:
                message["message"]["attachments"] = attachments
            
            # Send request
            response = requests.post(
                f"{self.BASE_URL}/me/sendMail",
                headers=self.headers,
                json=message,
                timeout=30
            )
            
            # Handle response
            if response.status_code == 202:
                logger.info(f"Email sent successfully to {to_email}")
                return {
                    "status": "success",
                    "message": "Email sent successfully",
                    "response_code": 202
                }

            # Map standard HTTP status codes
            status_descriptions = {
                400: "Bad Request: Malformed or incorrect request.",
                401: "Unauthorized: Missing or invalid authentication token.",
                402: "Payment Required: API payment requirements not met.",
                403: "Forbidden: Access denied. Insufficient permissions or license (check conditional access policies / insufficient_claims).",
                404: "Not Found: The requested resource doesn't exist.",
                405: "Method Not Allowed: HTTP method not allowed on this resource.",
                406: "Not Acceptable: Accept header format not supported.",
                409: "Conflict: Directory concurrency violation or resource conflict. Try again later.",
                410: "Gone: The requested resource is no longer available.",
                411: "Length Required: Content-Length header is missing.",
                412: "Precondition Failed: Resource state does not match request preconditions.",
                413: "Request Entity Too Large: Request exceeds maximum size limit.",
                415: "Unsupported Media Type: Unsupported request content type.",
                416: "Requested Range Not Satisfiable: Invalid raw range requested.",
                422: "Unprocessable Entity: Semantically incorrect request.",
                423: "Locked: The requested resource is locked.",
                429: "Too Many Requests: Throttled. Please retry after some delay.",
                500: "Internal Server Error: Internal server error.",
                501: "Not Implemented: Requested feature is not implemented.",
                503: "Service Unavailable: Service overloaded or undergoing maintenance.",
                504: "Gateway Timeout: Upstream server timed out.",
                507: "Insufficient Storage: Storage quota exceeded.",
                509: "Bandwidth Limit Exceeded: Bandwidth limit cap exceeded."
            }

            # Extract detailed error message from MS Graph error payload if available
            graph_error_code = None
            graph_error_message = None
            inner_error_code = None

            try:
                error_data = response.json()
                if isinstance(error_data, dict) and "error" in error_data:
                    err_dict = error_data["error"]
                    if isinstance(err_dict, dict):
                        graph_error_code = err_dict.get("code")
                        graph_error_message = err_dict.get("message")
                        # Handle innerError/innererror casing
                        inner_err = err_dict.get("innerError") or err_dict.get("innererror")
                        if isinstance(inner_err, dict):
                            inner_error_code = inner_err.get("code")
            except Exception:
                pass

            # Construct clean, detailed error message
            default_desc = status_descriptions.get(response.status_code, f"HTTP Error {response.status_code}")
            if graph_error_message:
                error_msg = graph_error_message
                if graph_error_code:
                    error_msg = f"[{graph_error_code}] {error_msg}"
                if inner_error_code:
                    error_msg += f" (Inner: {inner_error_code})"
            else:
                error_msg = f"{default_desc} (Raw: {response.text[:200]})"

            log_msg = f"Failed to send email to {to_email}: {error_msg}"
            
            if response.status_code == 401:
                logger.error(f"Unauthorized - token expired: {to_email}. Details: {error_msg}")
                return {
                    "status": "error",
                    "message": "Token expired",
                    "response_code": 401
                }
            elif response.status_code == 429:
                logger.warning(f"Rate limit exceeded for {to_email}. Details: {error_msg}")
                return {
                    "status": "error",
                    "message": "Rate limit exceeded",
                    "response_code": 429
                }
            else:
                logger.error(log_msg)
                return {
                    "status": "error",
                    "message": error_msg,
                    "response_code": response.status_code
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout sending email to {to_email}")
            return {
                "status": "error",
                "message": "Request timeout",
                "response_code": 408
            }
        except Exception as e:
            logger.error(f"Exception sending email to {to_email}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "response_code": 500
            }
    
    def test_connection(self) -> bool:
        """Test if the access token is valid"""
        try:
            response = requests.get(
                f"{self.BASE_URL}/me",
                headers=self.headers,
                timeout=10
            )
            return response.status_code == 200
        except:
            return False
