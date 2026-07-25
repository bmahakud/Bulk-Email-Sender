"""
Microsoft Graph Authentication using MSAL
"""
import os
import time
from typing import Optional, Dict
import msal
from loguru import logger


class GraphAuth:
    """Handle Microsoft Graph OAuth2 authentication"""
    
    SCOPES = [
        "User.Read",
        "Mail.Send",
        "offline_access"
    ]
    
    def __init__(self):
        self.client_id = os.getenv("CLIENT_ID")
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
        """Acquire token interactively (opens browser)"""
        try:
            result = self.app.acquire_token_interactive(
                scopes=self.SCOPES,
                parent_window_handle=None
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
                logger.error(f"Failed to acquire token: {result.get('error_description')}")
                return None
                
        except Exception as e:
            logger.error(f"Error acquiring token: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Dict]:
        """Refresh access token using refresh token"""
        try:
            result = self.app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=self.SCOPES
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
