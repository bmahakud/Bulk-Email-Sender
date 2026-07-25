"""
Modern Dashboard Tab
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QFrame, QTableWidget, QTableWidgetItem,
                               QHeaderView, QGroupBox, QGridLayout, QScrollArea)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor


class DashboardTab(QWidget):
    """Dashboard Overview"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #f5f6fa; }")
        
        # Content widget
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 50)
        
        # Title
        title = QLabel("Dashboard")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        layout.addWidget(title)
        
        subtitle = QLabel("Overview of your email campaigns")
        subtitle.setStyleSheet("color: #7f8c8d; font-size: 13px; margin-bottom: 10px;")
        layout.addWidget(subtitle)
        
        # Stats Cards - Compact Design
        stats_layout = QGridLayout()
        stats_layout.setSpacing(15)
        
        self.card_accounts = self.create_stat_card("Total SMTP Accounts", "0", "#5dade2", "📧")
        self.card_recipients = self.create_stat_card("Total Recipients", "0", "#a29bfe", "👥")
        self.card_sent = self.create_stat_card("Emails Sent Today", "0", "#55efc4", "✓")
        self.card_rate = self.create_stat_card("Success Rate", "0%", "#74b9ff", "📊")
        
        stats_layout.addWidget(self.card_accounts, 0, 0)
        stats_layout.addWidget(self.card_recipients, 0, 1)
        stats_layout.addWidget(self.card_sent, 0, 2)
        stats_layout.addWidget(self.card_rate, 0, 3)
        
        layout.addLayout(stats_layout)
        
        # Recent Activity Section - More Height
        activity_group = QGroupBox("Recent Activity")
        activity_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: 600;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 10px;
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
        activity_layout = QVBoxLayout()
        activity_layout.setContentsMargins(15, 15, 15, 15)
        
        activity_table = QTableWidget()
        activity_table.setColumnCount(4)
        activity_table.setHorizontalHeaderLabels(["Time", "Event", "Details", "Status"])
        activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        activity_table.setAlternatingRowColors(True)
        activity_table.verticalHeader().setVisible(False)
        activity_table.setStyleSheet("""
            QTableWidget {
                border: none;
                background-color: white;
                gridline-color: #f5f5f5;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                color: #5a6c7d;
                padding: 12px;
                font-weight: 600;
                border: none;
                border-bottom: 2px solid #e0e0e0;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 12px;
                color: #2c3e50;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #e8f4f8;
                color: #2c3e50;
            }
        """)
        
        # Sample activity data with softer status indicators
        activities = [
            ["12:45:30", "Email Sent", "user@example.com", "Success"],
            ["12:45:28", "Email Sent", "contact@company.com", "Success"],
            ["12:45:25", "SMTP Switch", "Account switched automatically", "Auto"],
            ["12:45:20", "Email Sent", "info@business.com", "Success"],
            ["12:40:15", "Campaign Started", "500 recipients loaded", "Running"],
            ["12:35:10", "Email Sent", "admin@test.com", "Success"],
            ["12:30:05", "SMTP Added", "New account configured", "Ready"],
        ]
        
        activity_table.setRowCount(len(activities))
        for row, data in enumerate(activities):
            for col, text in enumerate(data):
                item = QTableWidgetItem(text)
                item.setFont(QFont("Segoe UI", 11))
                
                # Softer status colors
                if col == 3:  # Status column
                    if "Success" in text:
                        item.setForeground(QColor("#55efc4"))
                    elif "Failed" in text or "Error" in text:
                        item.setForeground(QColor("#ff7675"))
                    elif "Running" in text:
                        item.setForeground(QColor("#74b9ff"))
                    else:
                        item.setForeground(QColor("#a29bfe"))
                
                activity_table.setItem(row, col, item)
        
        # Increase table height significantly
        activity_table.setMinimumHeight(350)
        activity_layout.addWidget(activity_table)
        activity_group.setLayout(activity_layout)
        layout.addWidget(activity_group)
        
        # Info Boxes - Subtle Design
        info_layout = QHBoxLayout()
        info_layout.setSpacing(15)
        
        info1 = self.create_info_box(
            "💡 Quick Tip",
            "Use Auto mode with delay settings for optimal email delivery",
            "#e3f2fd"
        )
        info2 = self.create_info_box(
            "⚡ System Status",
            "All systems operational. Ready to send emails.",
            "#e8f5e9"
        )
        
        info_layout.addWidget(info1)
        info_layout.addWidget(info2)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # Set scroll area
        scroll.setWidget(content)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def create_stat_card(self, title, value, color, icon):
        frame = QFrame()
        frame.setFixedHeight(120)  # Increased height
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid #e8e8e8;
                border-radius: 6px;
            }}
            QFrame:hover {{
                border: 1px solid {color};
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 18, 20, 18)
        
        # Icon and title row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI", 20))
        icon_label.setStyleSheet(f"color: {color};")
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #5a6c7d; font-size: 12px; font-weight: 600;")
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Value - Large and prominent
        value_label = QLabel(str(value))
        value_label.setFont(QFont("Segoe UI", 30, QFont.Bold))
        value_label.setStyleSheet(f"color: {color};")
        value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        value_label.setObjectName(f"value_{title.lower().replace(' ', '_')}")
        value_label.setMinimumHeight(40)  # Ensure minimum height for value
        layout.addWidget(value_label)
        
        return frame
    
    def create_info_box(self, title, text, bg_color):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: none;
                border-radius: 6px;
                padding: 18px;
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(8)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title_label.setStyleSheet("color: #2c3e50;")
        
        text_label = QLabel(text)
        text_label.setStyleSheet("color: #5a6c7d; font-size: 11px;")
        text_label.setWordWrap(True)
        
        layout.addWidget(title_label)
        layout.addWidget(text_label)
        
        return frame
