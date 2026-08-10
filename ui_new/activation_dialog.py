import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame, QStyle, QScrollArea, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QColor
from backend.license_validator import activate_license_online, get_machine_id

class ActivationDialog(QDialog):
    """
    A stunning, modern dark-themed activation screen for ProMailer Pro.
    Blocks application access until a valid key is activated or exits the application.
    """
    
    def __init__(self, parent=None, initial_status_msg=""):
        super().__init__(parent)
        self.setWindowTitle("ProMailer Pro Activation")
        self.setMinimumSize(560, 360)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False) # Force user to enter license or exit
        
        self.activation_successful = False
        self._init_ui(initial_status_msg)
        
    def _init_ui(self, status_msg):
        # Premium Dark Palette Stylesheet
        self.setStyleSheet("""
            QDialog, #container {
                background-color: #12131a;
                color: #e8eaf0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QScrollArea {
                background-color: #12131a;
                border: none;
            }
            QLabel {
                color: #e8eaf0;
            }
            QLineEdit {
                background-color: #1a1b27;
                border: 1px solid #3d3f52;
                border-radius: 6px;
                padding: 10px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 2px solid #5865f2;
                background-color: #212234;
            }
            QPushButton#btn_activate {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5865f2, stop:1 #4752c4);
                color: white;
                border: none;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btn_activate:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4752c4, stop:1 #3c45a5);
            }
            QPushButton#btn_activate:pressed {
                background-color: #3b4294;
            }
            QPushButton#btn_exit {
                background-color: #252637;
                color: #aab2c8;
                border: 1px solid #3d3f52;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#btn_exit:hover {
                background-color: #2e3046;
                color: white;
            }
            QFrame#card {
                background-color: #1a1b27;
                border: 1px solid #252637;
                border-radius: 8px;
            }
        """)
        
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create Scroll Area
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        
        # Container widget for scroll area
        container = QWidget()
        container.setObjectName("container")
        
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(15)
        
        # 1. Header (Logo / Titles)
        header_layout = QVBoxLayout()
        logo_lbl = QLabel("✉  ProMailer Pro")
        logo_lbl.setFont(QFont("Segoe UI", 22, QFont.Bold))
        logo_lbl.setStyleSheet("color: #5865f2; margin-bottom: 2px;")
        logo_lbl.setAlignment(Qt.AlignCenter)
        
        sub_lbl = QLabel("Software Licensing & Activation Check")
        sub_lbl.setFont(QFont("Segoe UI", 11))
        sub_lbl.setStyleSheet("color: #7289da;")
        sub_lbl.setAlignment(Qt.AlignCenter)
        
        header_layout.addWidget(logo_lbl)
        header_layout.addWidget(sub_lbl)
        main_layout.addLayout(header_layout)
        
        # Status Frame (if license is invalid/expired when launching)
        if status_msg:
            status_card = QFrame()
            status_card.setObjectName("card")
            sc_layout = QVBoxLayout(status_card)
            sc_layout.setContentsMargins(12, 12, 12, 12)
            
            sc_lbl = QLabel(status_msg)
            sc_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
            sc_lbl.setStyleSheet("color: #ed4245;")
            sc_lbl.setAlignment(Qt.AlignCenter)
            sc_lbl.setWordWrap(True)
            
            sc_layout.addWidget(sc_lbl)
            main_layout.addWidget(status_card)
            
        # 2. Form Container Card
        form_card = QFrame()
        form_card.setObjectName("card")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(15)
        
        # License key field
        key_lbl = QLabel("Enter License Key:")
        key_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("e.g. PM-XXXX-XXXX-XXXX")
        
        form_layout.addWidget(key_lbl)
        form_layout.addWidget(self.key_input)
        
        # Hardware ID display (for troubleshooting/manual key registration)
        hw_layout = QHBoxLayout()
        hw_lbl = QLabel("Your Machine ID:")
        hw_lbl.setFont(QFont("Segoe UI", 9))
        hw_lbl.setStyleSheet("color: #7880a0;")
        
        hw_val = QLineEdit(get_machine_id())
        hw_val.setReadOnly(True)
        hw_val.setFont(QFont("Courier New", 9))
        hw_val.setStyleSheet("""
            QLineEdit {
                background-color: #12131a; 
                border: none; 
                padding: 4px 6px; 
                color: #00d4aa;
            }
        """)
        hw_layout.addWidget(hw_lbl)
        hw_layout.addWidget(hw_val, 1)
        form_layout.addLayout(hw_layout)
        
        main_layout.addWidget(form_card)
        
        # 3. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.btn_exit = QPushButton("Exit Application")
        self.btn_exit.setObjectName("btn_exit")
        self.btn_exit.clicked.connect(self.reject)
        
        self.btn_activate = QPushButton("Activate Software")
        self.btn_activate.setObjectName("btn_activate")
        self.btn_activate.clicked.connect(self.on_activate_clicked)
        
        btn_layout.addWidget(self.btn_exit, 1)
        btn_layout.addWidget(self.btn_activate, 2)
        main_layout.addLayout(btn_layout)
        
        # Finalize layout wrapping
        scroll_area.setWidget(container)
        dialog_layout.addWidget(scroll_area)
        
    def on_activate_clicked(self):
        key = self.key_input.text().strip()
        
        if not key:
            QMessageBox.warning(self, "Validation Error", "Please enter your license key.")
            return
            
        self.btn_activate.setEnabled(False)
        self.btn_activate.setText("Activating online...")
        
        # Ping Server
        from backend.license_validator import DEFAULT_SERVER_URL
        success, msg = activate_license_online(key, DEFAULT_SERVER_URL)
        
        self.btn_activate.setEnabled(True)
        self.btn_activate.setText("Activate Software")
        
        if success:
            QMessageBox.information(self, "Success", "Software successfully activated! Welcome to ProMailer Pro.")
            self.activation_successful = True
            self.accept()
        else:
            QMessageBox.critical(self, "Activation Failed", msg)
