"""
Background worker for sending emails with QThread
"""
import time
from pathlib import Path
from typing import Optional, List, Dict
from PySide6.QtCore import QThread, Signal
from loguru import logger

from database.models import Account, Recipient, Campaign, SendLog
from graph.auth import GraphAuth
from graph.graph_client import GraphClient
from services.tag_engine import TagEngine
from services.html_parser import HTMLParser
from services.attachment import AttachmentProcessor


class SendWorker(QThread):
    """Background worker thread for sending emails"""
    
    # Signals for UI updates
    progress_updated = Signal(dict)  # {sent, failed, total, current_email, current_account}
    email_sent = Signal(dict)  # {recipient, status, message}
    account_switched = Signal(str)  # account_email
    campaign_completed = Signal(dict)  # {total, sent, failed, duration}
    error_occurred = Signal(str)  # error_message
    
    def __init__(self):
        super().__init__()
        self.campaign_id: Optional[int] = None
        self.recipients: List[Dict] = []
        self.html_content: str = ""
        self.subject_lines: List[str] = []
        self.attachments: List[Path] = []
        self.delay_seconds: float = 1.0
        self.retry_count: int = 3
        
        # Control flags
        self._running = False
        self._paused = False
        self._cancelled = False
        
        # State tracking
        self.current_account_index = 0
        self.sent_count = 0
        self.failed_count = 0
        self.start_time = 0
        
        self.auth = GraphAuth()
    
    def configure(self, campaign_id: int, recipients: List[Dict], html_content: str,
                  subject_lines: List[str], attachments: List[Path], 
                  delay_seconds: float = 1.0, retry_count: int = 3):
        """Configure worker with campaign details"""
        self.campaign_id = campaign_id
        self.recipients = recipients
        self.html_content = html_content
        self.subject_lines = subject_lines
        self.attachments = attachments
        self.delay_seconds = delay_seconds
        self.retry_count = retry_count
    
    def run(self):
        """Main worker thread execution"""
        self._running = True
        self._paused = False
        self._cancelled = False
        self.sent_count = 0
        self.failed_count = 0
        self.start_time = time.time()
        
        logger.info(f"Starting email send campaign {self.campaign_id}")
        Campaign.update_status(self.campaign_id, "running")
        
        # Get active accounts
        accounts = Account.get_active()
        if not accounts:
            self.error_occurred.emit("No active accounts available")
            Campaign.update_status(self.campaign_id, "failed")
            return
        
        # Process attachments once
        processed_attachments = AttachmentProcessor.process_attachments(self.attachments)
        
        # Send emails
        for idx, recipient in enumerate(self.recipients):
            # Check if cancelled
            if self._cancelled:
                logger.info("Campaign cancelled by user")
                Campaign.update_status(self.campaign_id, "cancelled")
                break
            
            # Wait if paused
            while self._paused and not self._cancelled:
                time.sleep(0.1)
            
            if self._cancelled:
                break
            
            # Try sending with retries
            success = False
            for attempt in range(self.retry_count):
                if self._cancelled:
                    break
                
                # Get current account
                account = accounts[self.current_account_index % len(accounts)]
                
                # Check token expiry and refresh if needed
                if self.auth.is_token_expired(account['token_expires_at']):
                    logger.info(f"Token expired for {account['email']}, refreshing...")
                    new_tokens = self.auth.refresh_access_token(account['refresh_token'])
                    if new_tokens:
                        Account.update_tokens(
                            account['email'],
                            new_tokens['access_token'],
                            new_tokens['refresh_token'],
                            new_tokens['expires_at']
                        )
                        account['access_token'] = new_tokens['access_token']
                    else:
                        logger.error(f"Failed to refresh token for {account['email']}")
                        Account.update_status(account['email'], 'token_expired')
                        self.current_account_index += 1
                        continue
                
                # Send email
                result = self._send_single_email(
                    account,
                    recipient,
                    processed_attachments,
                    idx
                )
                
                if result['status'] == 'success':
                    success = True
                    self.sent_count += 1
                    Campaign.increment_sent(self.campaign_id)
                    Recipient.update_status(recipient['id'], 'sent')
                    break
                elif result['response_code'] == 429:
                    # Rate limit - switch account
                    logger.warning(f"Rate limit hit for {account['email']}, switching account")
                    self.current_account_index += 1
                    self.account_switched.emit(accounts[self.current_account_index % len(accounts)]['email'])
                    time.sleep(2)  # Brief pause before retry
                elif result['response_code'] == 401:
                    # Token expired - try refresh
                    logger.warning(f"Token issue for {account['email']}, switching account")
                    self.current_account_index += 1
                    time.sleep(1)
                else:
                    # Other error - retry with same account
                    time.sleep(1)
            
            if not success:
                self.failed_count += 1
                Campaign.increment_failed(self.campaign_id)
                Recipient.update_status(recipient['id'], 'failed')
            
            # Emit progress
            self.progress_updated.emit({
                'sent': self.sent_count,
                'failed': self.failed_count,
                'total': len(self.recipients),
                'current_email': recipient['email'],
                'current_account': accounts[self.current_account_index % len(accounts)]['email']
            })
            
            # Delay between emails
            if idx < len(self.recipients) - 1:
                time.sleep(self.delay_seconds)
        
        # Campaign completed
        duration = time.time() - self.start_time
        Campaign.update_status(self.campaign_id, "completed")
        
        self.campaign_completed.emit({
            'total': len(self.recipients),
            'sent': self.sent_count,
            'failed': self.failed_count,
            'duration': duration
        })
        
        logger.info(f"Campaign {self.campaign_id} completed: {self.sent_count} sent, {self.failed_count} failed")
        self._running = False
    
    def _send_single_email(self, account: Dict, recipient: Dict, 
                          attachments: List[Dict], recipient_index: int) -> Dict:
        """Send a single email"""
        try:
            # Get subject (rotate through subject lines)
            subject = self.subject_lines[recipient_index % len(self.subject_lines)]
            
            # Replace tags in subject
            subject = TagEngine.replace_tags(subject, recipient)
            
            # Replace tags in HTML body
            body_html = TagEngine.replace_tags(self.html_content, recipient)
            
            # Send via Graph API
            client = GraphClient(account['access_token'])
            result = client.send_email(
                to_email=recipient['email'],
                subject=subject,
                body_html=body_html,
                attachments=attachments if attachments else None
            )
            
            # Log the send
            SendLog.create(
                campaign_id=self.campaign_id,
                recipient_email=recipient['email'],
                account_email=account['email'],
                subject=subject,
                status=result['status'],
                error_message=result.get('message') if result['status'] == 'error' else None,
                response_code=result.get('response_code')
            )
            
            # Update account stats if successful
            if result['status'] == 'success':
                Account.increment_sent(account['email'])
            
            # Emit signal
            self.email_sent.emit({
                'recipient': recipient['email'],
                'status': result['status'],
                'message': result.get('message', 'Success')
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending email to {recipient['email']}: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'response_code': 500
            }
    
    def pause(self):
        """Pause sending"""
        self._paused = True
        logger.info("Campaign paused")
    
    def resume(self):
        """Resume sending"""
        self._paused = False
        logger.info("Campaign resumed")
    
    def cancel(self):
        """Cancel sending"""
        self._cancelled = True
        logger.info("Campaign cancellation requested")
    
    def is_running(self) -> bool:
        """Check if worker is running"""
        return self._running
    
    def is_paused(self) -> bool:
        """Check if worker is paused"""
        return self._paused
