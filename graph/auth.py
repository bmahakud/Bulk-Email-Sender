"""
Microsoft Graph Authentication using MSAL
"""
import os
import time
import urllib.parse
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict
import msal
from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(override=True)


class AuthorizationCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if "code" in params:
            self.server.authorization_code = params["code"][0]
            msg = """
            <html>
            <head><title>Authentication Successful</title></head>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; text-align: center; padding-top: 100px; background-color: #f5f7fa; color: #2c3e50;">
                <div style="background-color: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); display: inline-block; max-width: 500px;">
                    <h1 style="color: #2ecc71;">✓ Authentication Successful!</h1>
                    <p style="font-size: 16px; margin: 20px 0;">You have successfully linked your Microsoft Account.</p>
                    <p style="color: #7f8c8d; font-size: 14px;">You can now close this browser window and return to the application.</p>
                </div>
            </body>
            </html>
            """
        else:
            msg = """
            <html>
            <head><title>Authentication Failed</title></head>
            <body style="font-family: 'Segoe UI', Arial, sans-serif; text-align: center; padding-top: 100px; background-color: #f5f7fa; color: #2c3e50;">
                <div style="background-color: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); display: inline-block; max-width: 500px;">
                    <h1 style="color: #e74c3c;">✗ Authentication Failed</h1>
                    <p style="font-size: 16px; margin: 20px 0;">No authorization code was found in the callback request.</p>
                    <p style="color: #7f8c8d; font-size: 14px;">Please try again.</p>
                </div>
            </body>
            </html>
            """
            
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(msg.encode("utf-8"))


class GraphAuth:
    """Handle Microsoft Graph OAuth2 authentication"""
    
    SCOPES = [
        "User.Read",
        "Mail.Send"
    ]
    
    def __init__(self, client_id: Optional[str] = None):
        self.client_id = client_id or os.getenv("CLIENT_ID")
        self.client_secret = os.getenv("CLIENT_SECRET")
        self.tenant_id = os.getenv("TENANT_ID", "common")
        self.redirect_uri = os.getenv("REDIRECT_URI", "http://localhost:8000/callback")
        
        if not self.client_id:
            raise ValueError("CLIENT_ID not found in environment variables")
        
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        
        # Create MSAL application
        self.app = msal.PublicClientApplication(
            client_id=self.client_id,
            authority=self.authority
        )
    
    def get_auth_url(self) -> str:
        """Get authorization URL for user login"""
        auth_url = self.app.get_authorization_request_url(
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        logger.info(f"Generated auth URL: {auth_url}")
        return auth_url
    
    def acquire_token_interactive(self) -> Optional[Dict]:
        """Acquire token interactively (by running a local callback listener)"""
        try:
            # 1. Generate auth URL
            auth_url = self.app.get_authorization_request_url(
                scopes=self.SCOPES,
                redirect_uri=self.redirect_uri
            )
            
            # 2. Parse port from redirect URI
            parsed_url = urllib.parse.urlparse(self.redirect_uri)
            port_val = parsed_url.port if parsed_url.port else 8000
            
            # 3. Start local redirect server
            server_address = ('', port_val)
            httpd = HTTPServer(server_address, AuthorizationCallbackHandler)
            httpd.authorization_code = None
            
            # Run serve_forever in a background thread
            server_thread = threading.Thread(target=httpd.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            # 4. Open browser
            logger.info("Opening browser for OAuth login...")
            webbrowser.open(auth_url)
            
            # 5. Wait for callback with Qt keep-alive loop
            try:
                from PySide6.QtCore import QCoreApplication
                has_qt = True
            except ImportError:
                has_qt = False
                
            start_time = time.time()
            timeout = 300  # 5 minutes
            
            while httpd.authorization_code is None:
                if has_qt:
                    QCoreApplication.processEvents()
                time.sleep(0.05)
                if time.time() - start_time > timeout:
                    httpd.shutdown()
                    httpd.server_close()
                    raise TimeoutError("OAuth login timed out after 5 minutes.")
            
            code = httpd.authorization_code
            httpd.shutdown()
            httpd.server_close()
            
            if not code:
                raise ValueError("Did not receive authorization code.")
                
            # 6. Exchange code for token
            logger.info("Exchanging authorization code for token...")
            result = self.app.acquire_token_by_authorization_code(
                code=code,
                scopes=self.SCOPES,
                redirect_uri=self.redirect_uri
            )
            
            if "access_token" in result:
                logger.info("Successfully acquired token interactively")
                return {
                    "access_token": result["access_token"],
                    "refresh_token": result.get("refresh_token"),
                    "expires_in": result.get("expires_in", 3600),
                    "expires_at": time.time() + result.get("expires_in", 3600)
                }
            else:
                err_desc = result.get('error_description') or result.get('error') or "Unknown MSAL Error"
                raise ValueError(f"MSAL Error: {err_desc}")
                
        except Exception as e:
            logger.error(f"Error acquiring token: {e}")
            raise e
    
    def acquire_token_client_credentials(self, client_secret: Optional[str] = None, tenant_id: Optional[str] = None) -> Optional[Dict]:
        """
        Acquire access token using Option A (Application Permissions / client_credentials flow):
        POST https://login.microsoftonline.com/<TENANT_ID>/oauth2/v2.0/token
        grant_type=client_credentials & scope=https://graph.microsoft.com/.default
        """
        import requests
        secret = (client_secret or self.client_secret or "").strip()
        tenant = (tenant_id or self.tenant_id or "").strip()
        if not secret or not tenant or tenant.lower() == "common":
            logger.error("client_credentials flow requires a valid client_secret and specific tenant_id")
            return None

        try:
            token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
            resp = requests.post(
                token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": secret,
                    "grant_type": "client_credentials",
                    "scope": "https://graph.microsoft.com/.default",
                },
                timeout=20,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code == 200 and "access_token" in data:
                logger.info("Successfully acquired token via client_credentials")
                return {
                    "access_token": data["access_token"],
                    "refresh_token": tenant,
                    "auth_flow": "client_credentials",
                    "expires_in": data.get("expires_in", 3600),
                    "expires_at": time.time() + data.get("expires_in", 3600),
                }
            logger.error(f"Failed client_credentials token: {data.get('error_description') or resp.text}")
            return None
        except Exception as e:
            logger.error(f"Error in acquire_token_client_credentials: {e}")
            return None

    def refresh_access_token(self, refresh_token: str, client_secret_hint: Optional[str] = None) -> Optional[Dict]:
        """
        Acquire fresh access token using either:
          1. Delegated OAuth2 Refresh Token (email|password|refresh_token|client_id)
          2. Application client_credentials (email|client_secret|tenant_id|client_id)
        """
        import re
        token_val = (refresh_token or "").strip()

        # Detect if token_val is a Tenant ID (UUID or domain) for Option A client_credentials flow
        is_uuid_tenant = bool(re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", token_val))
        is_domain_tenant = (
            "." in token_val and len(token_val) < 80 and not token_val.startswith(("M.", "0.", "1."))
        ) or token_val.lower() == "client_credentials"

        if is_uuid_tenant or is_domain_tenant:
            tenant = self.tenant_id if token_val.lower() == "client_credentials" else token_val
            secret = client_secret_hint or self.client_secret
            cc_res = self.acquire_token_client_credentials(client_secret=secret, tenant_id=tenant)
            if cc_res:
                return cc_res

        try:
            # Try initial refresh with configured application
            result = self.app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=self.SCOPES
            )
            
            # Smart Fallback: if tenant mismatch (AADSTS50020) or scope issue (AADSTS70000) is detected
            if "access_token" not in result:
                err_desc = result.get('error_description', '')
                if "AADSTS50020" in err_desc or "AADSTS70000" in err_desc:
                    logger.info("Access denied or scope expired. Retrying with 'common' tenant and '.default' scope...")
                    common_app = msal.PublicClientApplication(
                        client_id=self.client_id,
                        authority="https://login.microsoftonline.com/common"
                    )
                    result = common_app.acquire_token_by_refresh_token(
                        refresh_token=refresh_token,
                        scopes=["https://graph.microsoft.com/.default"]
                    )
            
            if "access_token" in result:
                logger.info("Successfully refreshed access token")
                return {
                    "access_token": result["access_token"],
                    "refresh_token": result.get("refresh_token", refresh_token),
                    "expires_in": result.get("expires_in", 3600),
                    "expires_at": time.time() + result.get("expires_in", 3600)
                }
            else:
                logger.error(f"Failed to refresh token: {result.get('error_description')}")
                return None
                
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return None
    
    def get_user_info(self, access_token: str) -> Optional[Dict]:
        """Get user profile information"""
        import requests
        
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(
                "https://graph.microsoft.com/v1.0/me",
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get user info: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None
    
    def is_token_expired(self, expires_at: float) -> bool:
        """Check if token is expired"""
        # Add 5 minute buffer
        return time.time() >= (expires_at - 300)
