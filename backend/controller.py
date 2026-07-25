"""
Controller to connect backend with UI
"""
from typing import List, Dict
from .database import Database
from .graph_api import GraphAPIClient
from .email_sender import EmailSenderWorker


class MailerController:
    """Main controller for the mailer application"""
    
    def __init__(self):
        self.db = Database()
        self.sender_worker = None
    
    # SMTP Account Methods
    def add_smtp_accounts(self, accounts_data: List[str]) -> int:
        """
        Add SMTP accounts from bulk paste
        Format: email|password|token|client_id
        Returns: Number of accounts added
        """
        added = 0
        for line in accounts_data:
            parts = line.strip().split('|')
            if len(parts) >= 4:
                email, password, token, client_id = parts[0], parts[1], parts[2], parts[3]
                self.db.add_smtp_account(email, password, token, client_id)
                added += 1
        return added
    
    def get_smtp_accounts(self) -> List[Dict]:
        """Get all SMTP accounts"""
        return self.db.get_smtp_accounts()
    
    def clear_smtp_accounts(self):
        """Clear all SMTP accounts"""
        self.db.clear_smtp_accounts()
    
    # Recipient Methods
    def add_recipients(self, recipients_data: List[tuple]) -> int:
        """
        Add recipients
        Format: [(email, name), ...]
        Returns: Number added
        """
        for email, name in recipients_data:
            self.db.add_recipient(email, name)
        return len(recipients_data)
    
    def get_recipients(self) -> List[Dict]:
        """Get all recipients"""
        return self.db.get_recipients()
    
    def clear_recipients(self):
        """Clear all recipients"""
        self.db.clear_recipients()
    
    # Sending Methods
    def start_campaign(self, config: Dict, callbacks: Dict):
        """
        Start email campaign
        
        config: {
            'delay': int (seconds),
            'mode': 'auto' or 'limit',
            'limit_per_smtp': int (for limit mode),
            'subject': str,
            'body': str (HTML),
            'client_id': str,
            'auto_remove': bool
        }
        
        callbacks: {
            'on_progress': function(data),
            'on_log': function(message),
            'on_finished': function()
        }
        """
        if self.sender_worker and self.sender_worker.isRunning():
            return False
        
        self.sender_worker = EmailSenderWorker(config)
        
        # Connect signals
        self.sender_worker.progress_updated.connect(callbacks['on_progress'])
        self.sender_worker.log_message.connect(callbacks['on_log'])
        self.sender_worker.finished.connect(callbacks['on_finished'])
        
        self.sender_worker.start()
        return True
    
    def pause_campaign(self):
        """Pause current campaign"""
        if self.sender_worker and self.sender_worker.isRunning():
            self.sender_worker.pause()
    
    def resume_campaign(self):
        """Resume paused campaign"""
        if self.sender_worker and self.sender_worker.isRunning():
            self.sender_worker.resume()
    
    def stop_campaign(self):
        """Stop current campaign"""
        if self.sender_worker and self.sender_worker.isRunning():
            self.sender_worker.stop()
            self.sender_worker.wait()
    
    # Statistics Methods
    def get_stats(self) -> Dict:
        """Get statistics"""
        return self.db.get_stats()
