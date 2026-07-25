#!/usr/bin/env python3
"""
Simple UI Demo - No Backend Logic
"""
import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QTabWidget, QLabel, QPushButton, 
                               QTableWidget, QTableWidgetItem, QTextEdit, QLineEdit,
                               QComboBox, QSpinBox, QCheckBox, QGroupBox, QFormLayout,
                               QProgressBar, QStatusBar)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class SimpleUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Outlook Bulk Mail Sender - UI Demo")
        self.setMinimumSize(1200, 800)
        self.init_ui()
    
    def init_ui(self):
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #2c3e50; padding: 15px;")
        header_layout = QHBoxLayout(header)
        title = QLabel("📧 Outlook Bulk Mail Sender")
        title.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        version = QLabel("v1.0.0")
        version.setStyleSheet("color: #bdc3c7;")
        header_layout.addWidget(version)
        layout.addWidget(header)
        
        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self.create_dashboard_tab(), "📊 Dashboard")
        tabs.addTab(self.create_accounts_tab(), "👤 Accounts")
        tabs.addTab(self.create_recipients_tab(), "📧 Recipients")
        tabs.addTab(self.create_templates_tab(), "📝 Templates")
        tabs.addTab(self.create_sender_tab(), "🚀 Sender")
        tabs.addTab(self.create_settings_tab(), "⚙️ Settings")
        layout.addWidget(tabs)
        
        # Status bar
        self.statusBar().showMessage("Ready - UI Demo Mode")
    
    def create_dashboard_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Stats cards
        stats_layout = QHBoxLayout()
        for title, value, color in [
            ("Total Accounts", "5", "#3498db"),
            ("Total Recipients", "1,234", "#2ecc71"),
            ("Emails Sent", "856", "#9b59b6"),
            ("Success Rate", "98.5%", "#e74c3c")
        ]:
            card = QGroupBox(title)
            card.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {color}; }}")
            card_layout = QVBoxLayout()
            value_label = QLabel(value)
            value_label.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {color};")
            value_label.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(value_label)
            card.setLayout(card_layout)
            stats_layout.addWidget(card)
        
        layout.addLayout(stats_layout)
        
        # Recent activity
        activity_group = QGroupBox("Recent Activity")
        activity_layout = QVBoxLayout()
        activity_text = QTextEdit()
        activity_text.setReadOnly(True)
        activity_text.setMaximumHeight(200)
        activity_text.setText("✓ Email sent to john@example.com\n✓ Email sent to jane@example.com\n✓ Campaign 'Product Launch' completed\n✓ New template 'Welcome Email' created")
        activity_layout.addWidget(activity_text)
        activity_group.setLayout(activity_layout)
        layout.addWidget(activity_group)
        
        layout.addStretch()
        return widget
    
    def create_accounts_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ Add Account")
        btn_refresh = QPushButton("🔄 Refresh")
        btn_remove = QPushButton("🗑️ Remove Selected")
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_refresh)
        btn_layout.addWidget(btn_remove)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Table
        table = QTableWidget(5, 6)
        table.setHorizontalHeaderLabels(["Email", "Status", "Daily Sent", "Total Sent", "Last Used", "Actions"])
        
        # Sample data
        sample_data = [
            ["user1@outlook.com", "Active", "12", "145", "2 hours ago"],
            ["user2@outlook.com", "Active", "8", "234", "1 hour ago"],
            ["user3@outlook.com", "Pending", "0", "0", "Never"],
            ["user4@outlook.com", "Active", "15", "567", "30 min ago"],
            ["user5@outlook.com", "Active", "5", "89", "3 hours ago"],
        ]
        
        for row, data in enumerate(sample_data):
            for col, value in enumerate(data):
                item = QTableWidgetItem(value)
                if col == 1:  # Status column
                    if value == "Active":
                        item.setForeground(Qt.green)
                    else:
                        item.setForeground(Qt.yellow)
                table.setItem(row, col, item)
            
            # Action button
            action_btn = QPushButton("Test Send")
            table.setCellWidget(row, 5, action_btn)
        
        table.resizeColumnsToContents()
        layout.addWidget(table)
        
        return widget
    
    def create_recipients_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_import = QPushButton("📁 Import CSV")
        btn_add = QPushButton("➕ Add Recipient")
        btn_clear = QPushButton("🗑️ Clear All")
        btn_layout.addWidget(btn_import)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Table
        table = QTableWidget(10, 6)
        table.setHorizontalHeaderLabels(["Email", "Name", "Company", "Invoice", "Status", "Actions"])
        
        # Sample data
        for row in range(10):
            table.setItem(row, 0, QTableWidgetItem(f"recipient{row+1}@example.com"))
            table.setItem(row, 1, QTableWidgetItem(f"Person {row+1}"))
            table.setItem(row, 2, QTableWidgetItem(f"Company {row+1}"))
            table.setItem(row, 3, QTableWidgetItem(f"INV-{1000+row}"))
            status = QTableWidgetItem("Pending" if row < 5 else "Sent")
            status.setForeground(Qt.yellow if row < 5 else Qt.green)
            table.setItem(row, 4, status)
            edit_btn = QPushButton("Edit")
            table.setCellWidget(row, 5, edit_btn)
        
        table.resizeColumnsToContents()
        layout.addWidget(table)
        
        return widget
    
    def create_templates_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_new = QPushButton("📝 New Template")
        btn_edit = QPushButton("✏️ Edit Selected")
        btn_delete = QPushButton("🗑️ Delete")
        btn_layout.addWidget(btn_new)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Templates list
        table = QTableWidget(3, 5)
        table.setHorizontalHeaderLabels(["Name", "Subject", "Attachments", "Created", "Actions"])
        
        templates = [
            ["Welcome Email", "Welcome to our service!", "logo.png", "2024-01-15"],
            ["Product Launch", "Exciting new product!", "product.pdf, banner.jpg", "2024-02-20"],
            ["Newsletter", "Monthly Newsletter - March", "none", "2024-03-01"]
        ]
        
        for row, data in enumerate(templates):
            for col, value in enumerate(data):
                table.setItem(row, col, QTableWidgetItem(value))
            preview_btn = QPushButton("👁️ Preview")
            table.setCellWidget(row, 4, preview_btn)
        
        table.resizeColumnsToContents()
        layout.addWidget(table)
        
        # Preview area
        preview_group = QGroupBox("Template Preview")
        preview_layout = QVBoxLayout()
        preview_text = QTextEdit()
        preview_text.setReadOnly(True)
        preview_text.setMaximumHeight(150)
        preview_text.setHtml("<h2>Welcome Email</h2><p>Dear {{name}},</p><p>Welcome to our service!</p>")
        preview_layout.addWidget(preview_text)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        return widget
    
    def create_sender_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Campaign settings
        settings_group = QGroupBox("Campaign Settings")
        form_layout = QFormLayout()
        
        campaign_name = QLineEdit()
        campaign_name.setPlaceholderText("Enter campaign name")
        form_layout.addRow("Campaign Name:", campaign_name)
        
        template_combo = QComboBox()
        template_combo.addItems(["Welcome Email", "Product Launch", "Newsletter"])
        form_layout.addRow("Template:", template_combo)
        
        delay_spin = QSpinBox()
        delay_spin.setRange(1, 60)
        delay_spin.setValue(5)
        delay_spin.setSuffix(" seconds")
        form_layout.addRow("Delay Between Emails:", delay_spin)
        
        daily_limit = QSpinBox()
        daily_limit.setRange(10, 500)
        daily_limit.setValue(100)
        form_layout.addRow("Daily Limit per Account:", daily_limit)
        
        test_mode = QCheckBox("Enable test mode (no actual sending)")
        form_layout.addRow("Test Mode:", test_mode)
        
        settings_group.setLayout(form_layout)
        layout.addWidget(settings_group)
        
        # Control buttons
        btn_layout = QHBoxLayout()
        btn_start = QPushButton("🚀 Start Campaign")
        btn_start.setStyleSheet("background-color: #2ecc71; color: white; padding: 10px; font-weight: bold;")
        btn_pause = QPushButton("⏸️ Pause")
        btn_stop = QPushButton("⏹️ Stop")
        btn_stop.setStyleSheet("background-color: #e74c3c; color: white; padding: 10px;")
        btn_layout.addWidget(btn_start)
        btn_layout.addWidget(btn_pause)
        btn_layout.addWidget(btn_stop)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Progress
        progress_group = QGroupBox("Campaign Progress")
        progress_layout = QVBoxLayout()
        
        progress_bar = QProgressBar()
        progress_bar.setValue(35)
        progress_layout.addWidget(progress_bar)
        
        stats_text = QLabel("Sent: 350 / 1000 | Success: 345 | Failed: 5 | Remaining: 650")
        stats_text.setStyleSheet("font-size: 14px; padding: 10px;")
        progress_layout.addWidget(stats_text)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # Live log
        log_group = QGroupBox("Live Log")
        log_layout = QVBoxLayout()
        log_text = QTextEdit()
        log_text.setReadOnly(True)
        log_text.setText("[12:30:45] ✓ Email sent to user1@example.com\n[12:30:50] ✓ Email sent to user2@example.com\n[12:30:55] ✗ Failed to send to user3@example.com - Rate limit\n[12:31:00] ✓ Email sent to user4@example.com")
        log_layout.addWidget(log_text)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        return widget
    
    def create_settings_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # API Settings
        api_group = QGroupBox("Microsoft Graph API Settings")
        api_layout = QFormLayout()
        
        client_id = QLineEdit()
        client_id.setPlaceholderText("Enter Client ID")
        api_layout.addRow("Client ID:", client_id)
        
        client_secret = QLineEdit()
        client_secret.setEchoMode(QLineEdit.Password)
        client_secret.setPlaceholderText("Enter Client Secret")
        api_layout.addRow("Client Secret:", client_secret)
        
        tenant_id = QLineEdit()
        tenant_id.setText("common")
        api_layout.addRow("Tenant ID:", tenant_id)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # Email Settings
        email_group = QGroupBox("Email Settings")
        email_layout = QFormLayout()
        
        rate_limit = QSpinBox()
        rate_limit.setRange(10, 500)
        rate_limit.setValue(100)
        email_layout.addRow("Daily Rate Limit:", rate_limit)
        
        retry_attempts = QSpinBox()
        retry_attempts.setRange(0, 5)
        retry_attempts.setValue(3)
        email_layout.addRow("Retry Attempts:", retry_attempts)
        
        timeout = QSpinBox()
        timeout.setRange(10, 120)
        timeout.setValue(30)
        timeout.setSuffix(" seconds")
        email_layout.addRow("Request Timeout:", timeout)
        
        email_group.setLayout(email_layout)
        layout.addWidget(email_group)
        
        # Save button
        btn_save = QPushButton("💾 Save Settings")
        btn_save.setStyleSheet("background-color: #3498db; color: white; padding: 10px; font-weight: bold;")
        layout.addWidget(btn_save)
        
        layout.addStretch()
        return widget


def main():
    app = QApplication(sys.argv)
    window = SimpleUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
