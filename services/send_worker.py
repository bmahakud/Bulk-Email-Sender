"""
Background worker for sending emails with QThread
"""
import time
import random
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
        self.body_templates: List[str] = []
        self.subject_lines: List[str] = []
        self.attachments: List[Path] = []
        self.delay_seconds: float = 1.0
        self.retry_count: int = 3
        self.rotation_mode: str = "randomized"
        self.emails_per_account: int = 100
        
        # Control flags
        self._running = False
        self._paused = False
        self._cancelled = False
        
        # State tracking
        self.current_account_index = 0
        self.current_account_sent = 0
        self.sent_count = 0
        self.failed_count = 0
        self.start_time = 0
        
        self.auth = GraphAuth()
    
    def configure(self, campaign_id: int, recipients: List[Dict], html_content: str,
                  subject_lines: List[str], attachments: List[Path], 
                  delay_seconds: float = 1.0, retry_count: int = 3,
                  body_templates: Optional[List[str]] = None,
                  rotation_mode: str = "randomized",
                  emails_per_account: int = 100):
        """Configure worker with campaign details"""
        self.campaign_id = campaign_id
        self.recipients = recipients
        self.html_content = html_content
        self.body_templates = body_templates if body_templates else ([html_content] if html_content else [])
        self.subject_lines = [s for s in subject_lines if s.strip()] if subject_lines else ["No Subject"]
        self.attachments = attachments
        self.delay_seconds = delay_seconds
        self.retry_count = retry_count
        self.rotation_mode = rotation_mode
        self.emails_per_account = emails_per_account
    
    def run(self):
        """Main worker thread execution"""
        self._running = True
        self._paused = False
        self._cancelled = False
        self.sent_count = 0
        self.failed_count = 0
        self.current_account_sent = 0
        self.start_time = time.time()
        
        logger.info(f"Starting email send campaign {self.campaign_id} (Mode: {self.rotation_mode})")
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
            
            # Check if current account reached batch threshold
            if (self.emails_per_account > 0 and 
                self.current_account_sent >= self.emails_per_account and 
                len(accounts) > 1):
                self.current_account_index += 1
                self.current_account_sent = 0
                new_acc = accounts[self.current_account_index % len(accounts)]
                logger.info(f"Switching account after {self.emails_per_account} sends -> {new_acc['email']}")
                self.account_switched.emit(new_acc['email'])
            
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
                        self.current_account_sent = 0
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
                    self.current_account_sent += 1
                    Campaign.increment_sent(self.campaign_id)
                    Recipient.update_status(recipient['id'], 'sent')
                    break
                elif result['response_code'] == 429:
                    # Rate limit - switch account
                    logger.warning(f"Rate limit hit for {account['email']}, switching account")
                    self.current_account_index += 1
                    self.current_account_sent = 0
                    self.account_switched.emit(accounts[self.current_account_index % len(accounts)]['email'])
                    time.sleep(2)  # Brief pause before retry
                elif result['response_code'] == 401:
                    # Token expired - try refresh
                    logger.warning(f"Token issue for {account['email']}, switching account")
                    self.current_account_index += 1
                    self.current_account_sent = 0
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
            
            # Responsive delay between emails
            if idx < len(self.recipients) - 1:
                end_sleep = time.time() + self.delay_seconds
                while time.time() < end_sleep and not self._cancelled:
                    while self._paused and not self._cancelled:
                        time.sleep(0.1)
                    time.sleep(0.1)
        
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
        """Send a single email with paired Subject + Body selection"""
        try:
            total_subjects = len(self.subject_lines) if self.subject_lines else 1
            bodies = self.body_templates if self.body_templates else ([self.html_content] if self.html_content else [""])
            total_bodies = len(bodies)
            num_pairs = max(total_subjects, total_bodies)
            
            if self.rotation_mode in ("randomized", "random"):
                # Randomized: Pick random pair on EVERY individual email
                pair_index = random.randint(0, num_pairs - 1)
            elif self.rotation_mode == "per_smtp":
                # Per SMTP: Locked to active SMTP account index (switches when account rotates)
                pair_index = self.current_account_index % num_pairs
            else:
                # Per Email (Default): Rotates sequentially per email (1 -> 2 -> 3 -> 4 -> 1...)
                pair_index = (self.sent_count + self.failed_count) % num_pairs
            
            subject_raw = self.subject_lines[pair_index % total_subjects]
            body_raw = bodies[pair_index % total_bodies]
            
            # Replace tags in subject & body
            subject = TagEngine.replace_tags(subject_raw, recipient)
            body_replaced = TagEngine.replace_tags(body_raw, recipient)
            
            # If body is plain text, wrap newlines nicely for HTML email clients
            if "<html" not in body_replaced.lower() and "<p" not in body_replaced.lower() and "<div" not in body_replaced.lower():
                body_html = "<div style='font-family: Arial, Helvetica, sans-serif; font-size: 14px; line-height: 1.6; color: #222;'>" + body_replaced.replace("\n", "<br>") + "</div>"
            else:
                body_html = body_replaced
            
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
        logger.info("SendWorker: Paused")

    def resume(self):
        """Resume sending"""
        self._paused = False
        logger.info("SendWorker: Resumed")

    def cancel(self):
        """Cancel and stop sending"""
        self._cancelled = True
        self._running = False
        self._paused = False
        logger.info("SendWorker: Cancelled")

    def stop(self):
        """Stop alias for cancel"""
        self.cancel()

