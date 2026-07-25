"""
Modern Main Window - Outlook Bulk Mail Sender
"""
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QTabWidget,
                               QLabel, QStatusBar, QHBoxLayout)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon

from ui_modern.accounts import AccountsTab
from ui_modern.recipients import RecipientsTab
from ui_modern.sender import SenderTab
from ui_modern.dashboard import DashboardTab
from ui_modern.settings import SettingsTab
from ui_modern.templates import TemplatesTab


class MainWindow(QMainWindow):
    """Modern Main Application Window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Outlook Bulk Mail Sender - Professional Edition")
        self.setMinimumSize(1400, 900)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f6fa;
            }
        """)
        
        self.init_ui()
    
    def init_ui(self):
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = self.create_header()
        layout.addWidget(header)
        
        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #f5f6fa;
            }
            QTabBar::tab {
                background-color: #1a1a2e;
                color: #aaa;
                padding: 14px 28px;
                margin-right: 2px;
                border: none;
                font-size: 13px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #16213e;
                color: #fff;
                border-bottom: 3px solid #4ecca3;
            }
            QTabBar::tab:hover {
                background-color: #16213e;
                color: #ddd;
            }
        """)
        
        # Create tabs
        self.dashboard_tab = DashboardTab()
        self.accounts_tab = AccountsTab()
        self.recipients_tab = RecipientsTab()
        self.templates_tab = TemplatesTab()
        self.sender_tab = SenderTab()
        self.settings_tab = SettingsTab()
        
        # Add tabs
        self.tabs.addTab(self.dashboard_tab, "📊 Dashboard")
        self.tabs.addTab(self.accounts_tab, "📧 SMTP Accounts")
        self.tabs.addTab(self.recipients_tab, "📨 Recipients")
        self.tabs.addTab(self.templates_tab, "📝 Templates")
        self.tabs.addTab(self.sender_tab, "🚀 Send Emails")
        self.tabs.addTab(self.settings_tab, "⚙️ Settings")
        
        layout.addWidget(self.tabs)
        
        # Status Bar
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #1a1a2e;
                color: #aaa;
                padding: 6px;
                font-size: 11px;
                border-top: 1px solid #16213e;
            }
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("✓ System Ready")
    
    def create_header(self):
        header = QWidget()
        header.setFixedHeight(70)
        header.setStyleSheet("""
            QWidget {
                background-color: #1a1a2e;
                border-bottom: 2px solid #16213e;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(30, 10, 30, 10)
        
        # Logo/Title
        title = QLabel("✉ Outlook Bulk Mail Sender")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #eee; border: none;")
        
        layout.addWidget(title)
        layout.addStretch()
        
        # Status indicator
        status = QLabel("● Online")
        status.setStyleSheet("color: #4ecca3; font-size: 12px; border: none;")
        layout.addWidget(status)
        
        # Version
        version = QLabel("v2.0")
        version.setStyleSheet("color: #888; font-size: 11px; margin-left: 20px; border: none;")
        layout.addWidget(version)
        
        return header
