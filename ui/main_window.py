"""
Main application window
"""
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QTabWidget, QLabel, QStatusBar)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from loguru import logger

from ui.dashboard import DashboardTab
from ui.accounts import AccountsTab
from ui.recipients import RecipientsTab
from ui.templates import TemplatesTab
from ui.sender import SenderTab
from ui.settings import SettingsTab
from ui.logs import LogsTab


class MainWindow(QMainWindow):
    """Main application window with tabs"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Outlook Bulk Mail Sender")
        self.setMinimumSize(1200, 800)
        
        self.init_ui()
        logger.info("Main window initialized")
    
    def init_ui(self):
        """Initialize the user interface"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        
        # Create tabs
        self.dashboard_tab = DashboardTab()
        self.accounts_tab = AccountsTab()
        self.recipients_tab = RecipientsTab()
        self.templates_tab = TemplatesTab()
        self.sender_tab = SenderTab()
        self.settings_tab = SettingsTab()
        self.logs_tab = LogsTab()
        
        # Add tabs
        self.tabs.addTab(self.dashboard_tab, "📊 Dashboard")
        self.tabs.addTab(self.accounts_tab, "👤 Accounts")
        self.tabs.addTab(self.recipients_tab, "📧 Recipients")
        self.tabs.addTab(self.templates_tab, "📝 Templates")
        self.tabs.addTab(self.sender_tab, "🚀 Sender")
        self.tabs.addTab(self.settings_tab, "⚙️ Settings")
        self.tabs.addTab(self.logs_tab, "📋 Logs")
        
        layout.addWidget(self.tabs)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def _create_header(self) -> QWidget:
        """Create header widget"""
        header = QWidget()
        header.setStyleSheet("background-color: #2c3e50; padding: 10px;")
        
        layout = QHBoxLayout(header)
        
        # Title
        title = QLabel("Outlook Bulk Mail Sender")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        # Version
        version = QLabel("v1.0.0")
        version.setStyleSheet("color: #bdc3c7; font-size: 12px;")
        layout.addWidget(version)
        
        return header
