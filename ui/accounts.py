"""
Accounts tab - Manage Outlook/Hotmail accounts
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QLabel, QMessageBox)
from PySide6.QtCore import Qt
from loguru import logger

from database.models import Account
from graph.auth import GraphAuth


class AccountsTab(QWidget):
    """Accounts management tab"""
    
    def __init__(self):
        super().__init__()
        self.auth = GraphAuth()
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Accounts Management")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        # Add account button
        add_btn = QPushButton("➕ Add Account")
        add_btn.clicked.connect(self.add_account)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
        """)
        header.addWidget(add_btn)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_accounts)
        header.addWidget(refresh_btn)
        
        layout.addLayout(header)
        
        # Accounts table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Email", "Status", "Daily Sent", "Total Sent", "Last Used", "Actions"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)
        
        # Load accounts
        self.load_accounts()
    
    def add_account(self):
        """Add new Outlook account"""
        try:
            logger.info("Initiating account authentication")
            
            # Open browser for authentication
            result = self.auth.acquire_token_interactive()
            
            if result:
                # Get user info
                user_info = self.auth.get_user_info(result['access_token'])
                
                if user_info:
                    email = user_info.get('userPrincipalName') or user_info.get('mail')
                    
                    # Create account in database
                    account_id = Account.create(email)
                    
                    # Update with tokens
                    Account.update_tokens(
                        email,
                        result['access_token'],
                        result['refresh_token'],
                        result['expires_at']
                    )
                    
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Account {email} added successfully!"
                    )
                    
                    logger.info(f"Account added: {email}")
                    self.load_accounts()
                else:
                    QMessageBox.warning(self, "Error", "Failed to get user information")
            else:
                QMessageBox.warning(self, "Error", "Authentication failed")
                
        except Exception as e:
            logger.error(f"Error adding account: {e}")
            QMessageBox.critical(self, "Error", f"Failed to add account: {str(e)}")
    
    def load_accounts(self):
        """Load and display accounts"""
        try:
            accounts = Account.get_all()
            
            self.table.setRowCount(len(accounts))
            
            for row, account in enumerate(accounts):
                # Email
                self.table.setItem(row, 0, QTableWidgetItem(account['email']))
                
                # Status
                status_item = QTableWidgetItem(account['status'])
                if account['status'] == 'active':
                    status_item.setForeground(Qt.green)
                elif account['status'] == 'token_expired':
                    status_item.setForeground(Qt.red)
                self.table.setItem(row, 1, status_item)
                
                # Daily sent
                self.table.setItem(row, 2, QTableWidgetItem(str(account['daily_sent'])))
                
                # Total sent
                self.table.setItem(row, 3, QTableWidgetItem(str(account['total_sent'])))
                
                # Last used
                last_used = account['last_used'] if account['last_used'] else "Never"
                self.table.setItem(row, 4, QTableWidgetItem(str(last_used)))
                
                # Actions (placeholder)
                self.table.setItem(row, 5, QTableWidgetItem(""))
            
            self.table.resizeColumnsToContents()
            
        except Exception as e:
            logger.error(f"Error loading accounts: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load accounts: {str(e)}")
