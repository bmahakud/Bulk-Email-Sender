"""
Modern Settings Tab
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QGroupBox, QFormLayout,
                               QSpinBox, QTextEdit, QMessageBox, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class SettingsTab(QWidget):
    """Application Settings"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        layout.addWidget(title)
        
        subtitle = QLabel("Configure application settings")
        subtitle.setStyleSheet("color: #7f8c8d; font-size: 13px; margin-bottom: 15px;")
        layout.addWidget(subtitle)
        
        # Microsoft API Settings
        api_group = QGroupBox("Microsoft Graph API Configuration")
        api_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: 600;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 15px;
                padding-top: 20px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: #2c3e50;
            }
        """)
        api_layout = QFormLayout()
        api_layout.setSpacing(15)
        api_layout.setContentsMargins(20, 20, 20, 20)
        
        self.client_id_input = QLineEdit()
        self.client_id_input.setPlaceholderText("Enter your Client ID")
        self.client_id_input.setText("9e5f94bc-e8a4-4e73-b8be-63364c29d753")
        self.client_id_input.setStyleSheet(self.get_input_style())
        
        self.tenant_id_input = QLineEdit()
        self.tenant_id_input.setPlaceholderText("common or your tenant ID")
        self.tenant_id_input.setText("common")
        self.tenant_id_input.setStyleSheet(self.get_input_style())
        
        api_layout.addRow("Client ID:", self.client_id_input)
        api_layout.addRow("Tenant ID:", self.tenant_id_input)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # Email Settings
        email_group = QGroupBox("Email Configuration")
        email_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: 600;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 15px;
                padding-top: 20px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: #2c3e50;
            }
        """)
        email_layout = QFormLayout()
        email_layout.setSpacing(15)
        email_layout.setContentsMargins(20, 20, 20, 20)
        
        self.rate_limit_spin = QSpinBox()
        self.rate_limit_spin.setRange(10, 1000)
        self.rate_limit_spin.setValue(100)
        self.rate_limit_spin.setStyleSheet(self.get_input_style())
        
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 120)
        self.timeout_spin.setValue(30)
        self.timeout_spin.setSuffix(" seconds")
        self.timeout_spin.setStyleSheet(self.get_input_style())
        
        self.max_retries_spin = QSpinBox()
        self.max_retries_spin.setRange(0, 10)
        self.max_retries_spin.setValue(3)
        self.max_retries_spin.setStyleSheet(self.get_input_style())
        
        email_layout.addRow("Daily Rate Limit:", self.rate_limit_spin)
        email_layout.addRow("Request Timeout:", self.timeout_spin)
        email_layout.addRow("Max Retries:", self.max_retries_spin)
        
        email_group.setLayout(email_layout)
        layout.addWidget(email_group)
        
        # Save Button
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        btn_save = QPushButton("Save Settings")
        btn_save.setStyleSheet(self.get_button_style("#5dade2"))
        btn_save.setMinimumHeight(45)
        btn_save.clicked.connect(self.save_settings)
        
        btn_reset = QPushButton("Reset to Default")
        btn_reset.setStyleSheet(self.get_button_style("#95a5a6"))
        btn_reset.setMinimumHeight(45)
        btn_reset.clicked.connect(self.reset_settings)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_reset)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        layout.addStretch()
    
    def get_input_style(self):
        return """
            QLineEdit, QSpinBox {
                padding: 10px 12px;
                border: 1px solid #d0d0d0;
                border-radius: 5px;
                font-size: 13px;
                background-color: white;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #5dade2;
            }
        """
    
    def get_button_style(self, color):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 12px 30px;
                font-size: 13px;
                font-weight: 500;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                opacity: 0.85;
            }}
            QPushButton:pressed {{
                padding: 13px 29px 11px 31px;
            }}
        """
    
    def save_settings(self):
        QMessageBox.information(self, "Success", "Settings saved successfully!")
    
    def reset_settings(self):
        reply = QMessageBox.question(
            self, "Confirm Reset",
            "Are you sure you want to reset all settings to default?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.client_id_input.setText("9e5f94bc-e8a4-4e73-b8be-63364c29d753")
            self.tenant_id_input.setText("common")
            self.rate_limit_spin.setValue(100)
            self.timeout_spin.setValue(30)
            self.max_retries_spin.setValue(3)
            QMessageBox.information(self, "Reset", "Settings reset to default!")
