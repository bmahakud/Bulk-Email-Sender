"""
Sender tab - Send emails with progress tracking
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QProgressBar, QTextEdit, QMessageBox,
                               QSpinBox, QDoubleSpinBox, QFormLayout, QGroupBox)
from PySide6.QtCore import Qt
import time
from loguru import logger

from database.models import Campaign, Recipient, get_connection
from services.send_worker import SendWorker


class SenderTab(QWidget):
    """Email sender tab with progress tracking"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.current_campaign_id = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Campaign Sender")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        
        # Settings group
        settings_group = QGroupBox("Campaign Settings")
        settings_layout = QFormLayout(settings_group)
        
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.1, 60.0)
        self.delay_spin.setValue(1.0)
        self.delay_spin.setSuffix(" seconds")
        settings_layout.addRow("Delay between emails:", self.delay_spin)
        
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        self.retry_spin.setValue(3)
        settings_layout.addRow("Retry count:", self.retry_spin)
        
        layout.addWidget(settings_group)
        
        # Control buttons
        controls = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 Start Campaign")
        self.start_btn.clicked.connect(self.start_campaign)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 15px 30px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        controls.addWidget(self.start_btn)
        
        self.pause_btn = QPushButton("⏸️ Pause")
        self.pause_btn.clicked.connect(self.pause_campaign)
        self.pause_btn.setEnabled(False)
        controls.addWidget(self.pause_btn)
        
        self.resume_btn = QPushButton("▶️ Resume")
        self.resume_btn.clicked.connect(self.resume_campaign)
        self.resume_btn.setEnabled(False)
        controls.addWidget(self.resume_btn)
        
        self.stop_btn = QPushButton("⏹️ Stop")
        self.stop_btn.clicked.connect(self.stop_campaign)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #e74c3c; color: white; padding: 15px 30px;")
        controls.addWidget(self.stop_btn)
        
        layout.addLayout(controls)
        
        # Progress section
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)
        
        # Stats
        stats = QHBoxLayout()
        
        self.sent_label = QLabel("Sent: 0")
        self.sent_label.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 14px;")
        stats.addWidget(self.sent_label)
        
        self.failed_label = QLabel("Failed: 0")
        self.failed_label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 14px;")
        stats.addWidget(self.failed_label)
        
        self.total_label = QLabel("Total: 0")
        self.total_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        stats.addWidget(self.total_label)
        
        progress_layout.addLayout(stats)
        
        # Current status
        self.status_label = QLabel("Status: Ready")
        self.status_label.setStyleSheet("font-style: italic;")
        progress_layout.addWidget(self.status_label)
        
        self.current_email_label = QLabel("Current: -")
        progress_layout.addWidget(self.current_email_label)
        
        self.current_account_label = QLabel("Account: -")
        progress_layout.addWidget(self.current_account_label)
        
        layout.addWidget(progress_group)
        
        # Log output
        log_label = QLabel("Live Log:")
        log_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        layout.addWidget(self.log_text)
    
    def start_campaign(self):
        """Start sending campaign"""
        try:
            from ui.templates import TemplatesTab
            
            # Validate prerequisites
            from database.models import Account
            accounts = Account.get_active()
            if not accounts:
                QMessageBox.warning(self, "Error", "No active accounts. Please add an account first.")
                return
            
            # Get recipients
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recipients WHERE status = 'pending' LIMIT 5000")
            recipients = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            if not recipients:
                QMessageBox.warning(self, "Error", "No recipients found. Please import recipients first.")
                return
            
            # Get template from templates tab
            main_window = self.window()
            templates_tab = main_window.findChild(TemplatesTab)
            if not templates_tab:
                QMessageBox.warning(self, "Error", "Cannot access templates")
                return
            
            template_data = templates_tab.get_template_data()
            if not template_data['html'] or not template_data['subjects']:
                QMessageBox.warning(self, "Error", "Please configure HTML template and subject lines first.")
                return
            
            # Create campaign
            self.current_campaign_id = Campaign.create(f"Campaign_{int(time.time())}")
            
            # Update recipient campaign IDs
            for recipient in recipients:
                from database.models import get_connection
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE recipients SET campaign_id = ? WHERE id = ?", 
                             (self.current_campaign_id, recipient['id']))
                conn.commit()
                conn.close()
            
            # Configure worker
            self.worker = SendWorker()
            self.worker.configure(
                campaign_id=self.current_campaign_id,
                recipients=recipients,
                html_content=template_data['html'],
                subject_lines=template_data['subjects'],
                attachments=[],  # TODO: Add attachment support
                delay_seconds=self.delay_spin.value(),
                retry_count=self.retry_spin.value()
            )
            
            # Connect signals
            self.worker.progress_updated.connect(self.on_progress_updated)
            self.worker.email_sent.connect(self.on_email_sent)
            self.worker.account_switched.connect(self.on_account_switched)
            self.worker.campaign_completed.connect(self.on_campaign_completed)
            self.worker.error_occurred.connect(self.on_error)
            
            # Update UI
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.total_label.setText(f"Total: {len(recipients)}")
            self.status_label.setText("Status: Running...")
            
            # Start worker
            self.worker.start()
            
            self.add_log("✓ Campaign started")
            logger.info(f"Campaign {self.current_campaign_id} started with {len(recipients)} recipients")
            
        except Exception as e:
            logger.error(f"Error starting campaign: {e}")
            QMessageBox.critical(self, "Error", f"Failed to start campaign: {str(e)}")
    
    def pause_campaign(self):
        """Pause campaign"""
        if self.worker:
            self.worker.pause()
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(True)
            self.status_label.setText("Status: Paused")
            self.add_log("⏸️ Campaign paused")
    
    def resume_campaign(self):
        """Resume campaign"""
        if self.worker:
            self.worker.resume()
            self.pause_btn.setEnabled(True)
            self.resume_btn.setEnabled(False)
            self.status_label.setText("Status: Running...")
            self.add_log("▶️ Campaign resumed")
    
    def stop_campaign(self):
        """Stop campaign"""
        if self.worker:
            self.worker.cancel()
            self.start_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.status_label.setText("Status: Stopped")
            self.add_log("⏹️ Campaign stopped")
    
    def on_progress_updated(self, data: dict):
        """Handle progress update"""
        sent = data['sent']
        failed = data['failed']
        total = data['total']
        
        self.sent_label.setText(f"Sent: {sent}")
        self.failed_label.setText(f"Failed: {failed}")
        
        progress = int((sent + failed) / total * 100) if total > 0 else 0
        self.progress_bar.setValue(progress)
        
        self.current_email_label.setText(f"Current: {data['current_email']}")
        self.current_account_label.setText(f"Account: {data['current_account']}")
    
    def on_email_sent(self, data: dict):
        """Handle email sent event"""
        status_icon = "✓" if data['status'] == 'success' else "✗"
        self.add_log(f"{status_icon} {data['recipient']}: {data['message']}")
    
    def on_account_switched(self, account_email: str):
        """Handle account switch"""
        self.add_log(f"🔄 Switched to account: {account_email}")
    
    def on_campaign_completed(self, data: dict):
        """Handle campaign completion"""
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Status: Completed")
        
        duration_min = data['duration'] / 60
        self.add_log(f"\n✓ Campaign completed in {duration_min:.1f} minutes")
        self.add_log(f"  Sent: {data['sent']}, Failed: {data['failed']}, Total: {data['total']}")
        
        QMessageBox.information(
            self,
            "Campaign Completed",
            f"Campaign completed successfully!\n\nSent: {data['sent']}\nFailed: {data['failed']}\nTotal: {data['total']}\nDuration: {duration_min:.1f} minutes"
        )
    
    def on_error(self, error_message: str):
        """Handle error"""
        self.add_log(f"ERROR: {error_message}")
        QMessageBox.critical(self, "Error", error_message)
    
    def add_log(self, message: str):
        """Add message to log"""
        import time
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
