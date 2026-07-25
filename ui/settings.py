"""
Settings tab - Application configuration
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QSpinBox,
                               QDoubleSpinBox, QLabel, QPushButton, QMessageBox,
                               QGroupBox)
from PySide6.QtCore import Qt


class SettingsTab(QWidget):
    """Settings configuration tab"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        
        # Title
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        
        # Sending settings
        sending_group = QGroupBox("Sending Settings")
        sending_layout = QFormLayout(sending_group)
        
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.1, 60.0)
        self.delay_spin.setValue(1.0)
        self.delay_spin.setSuffix(" seconds")
        sending_layout.addRow("Default delay between emails:", self.delay_spin)
        
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 100)
        self.batch_spin.setValue(10)
        sending_layout.addRow("Batch size:", self.batch_spin)
        
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(0, 10)
        self.retry_spin.setValue(3)
        sending_layout.addRow("Retry count:", self.retry_spin)
        
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 5)
        self.thread_spin.setValue(1)
        sending_layout.addRow("Thread count:", self.thread_spin)
        
        layout.addWidget(sending_group)
        
        # Rate limit settings
        rate_group = QGroupBox("Rate Limit Settings")
        rate_layout = QFormLayout(rate_group)
        
        self.daily_limit_spin = QSpinBox()
        self.daily_limit_spin.setRange(10, 10000)
        self.daily_limit_spin.setValue(300)
        rate_layout.addRow("Daily limit per account:", self.daily_limit_spin)
        
        self.hourly_limit_spin = QSpinBox()
        self.hourly_limit_spin.setRange(5, 100)
        self.hourly_limit_spin.setValue(30)
        rate_layout.addRow("Hourly limit per account:", self.hourly_limit_spin)
        
        layout.addWidget(rate_group)
        
        # Save button
        save_btn = QPushButton("💾 Save Settings")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        layout.addWidget(save_btn)
        
        layout.addStretch()
    
    def save_settings(self):
        """Save settings to database"""
        try:
            from database.models import get_connection
            
            settings = {
                'delay_seconds': self.delay_spin.value(),
                'batch_size': self.batch_spin.value(),
                'retry_count': self.retry_spin.value(),
                'thread_count': self.thread_spin.value(),
                'daily_limit': self.daily_limit_spin.value(),
                'hourly_limit': self.hourly_limit_spin.value()
            }
            
            conn = get_connection()
            cursor = conn.cursor()
            
            for key, value in settings.items():
                cursor.execute("""
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, julianday('now'))
                """, (key, str(value)))
            
            conn.commit()
            conn.close()
            
            QMessageBox.information(self, "Success", "Settings saved successfully!")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")
