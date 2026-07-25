"""
Dashboard tab - Overview of system status
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QGroupBox, QGridLayout)
from PySide6.QtCore import Qt, QTimer
from database.models import Account, Campaign, get_connection


class DashboardTab(QWidget):
    """Dashboard overview tab"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_stats)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        
        # Title
        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 24px; font-weight: bold; padding: 20px;")
        layout.addWidget(title)
        
        # Stats grid
        stats_layout = QGridLayout()
        
        # Accounts stats
        self.accounts_group = self._create_stat_box("Accounts", "0", "Active accounts")
        stats_layout.addWidget(self.accounts_group, 0, 0)
        
        # Recipients stats
        self.recipients_group = self._create_stat_box("Recipients", "0", "Total recipients")
        stats_layout.addWidget(self.recipients_group, 0, 1)
        
        # Campaigns stats
        self.campaigns_group = self._create_stat_box("Campaigns", "0", "Total campaigns")
        stats_layout.addWidget(self.campaigns_group, 0, 2)
        
        # Sent today
        self.sent_today_group = self._create_stat_box("Sent Today", "0", "Emails sent today")
        stats_layout.addWidget(self.sent_today_group, 1, 0)
        
        # Total sent
        self.total_sent_group = self._create_stat_box("Total Sent", "0", "All time emails")
        stats_layout.addWidget(self.total_sent_group, 1, 1)
        
        # Success rate
        self.success_rate_group = self._create_stat_box("Success Rate", "0%", "Overall success")
        stats_layout.addWidget(self.success_rate_group, 1, 2)
        
        layout.addLayout(stats_layout)
        
        # Refresh stats
        self.refresh_stats()
    
    def _create_stat_box(self, title: str, value: str, description: str) -> QGroupBox:
        """Create a stat display box"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                padding: 15px;
                margin: 10px;
            }
        """)
        
        layout = QVBoxLayout(group)
        
        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #3498db;")
        value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(value_label)
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)
        
        return group
    
    def refresh_stats(self):
        """Refresh dashboard statistics"""
        try:
            # Get accounts count
            accounts = Account.get_all()
            active_accounts = [a for a in accounts if a['status'] == 'active']
            self._update_stat_value(self.accounts_group, str(len(active_accounts)))
            
            # Get database stats
            conn = get_connection()
            cursor = conn.cursor()
            
            # Recipients count
            cursor.execute("SELECT COUNT(*) FROM recipients")
            recipients_count = cursor.fetchone()[0]
            self._update_stat_value(self.recipients_group, str(recipients_count))
            
            # Campaigns count
            cursor.execute("SELECT COUNT(*) FROM campaigns")
            campaigns_count = cursor.fetchone()[0]
            self._update_stat_value(self.campaigns_group, str(campaigns_count))
            
            # Total sent
            total_sent = sum(a['total_sent'] for a in accounts)
            self._update_stat_value(self.total_sent_group, str(total_sent))
            
            # Sent today (placeholder - would need date filtering)
            cursor.execute("SELECT COUNT(*) FROM send_logs WHERE status = 'success' AND date(sent_at) = date('now')")
            sent_today = cursor.fetchone()[0]
            self._update_stat_value(self.sent_today_group, str(sent_today))
            
            # Success rate
            cursor.execute("SELECT COUNT(*) FROM send_logs WHERE status = 'success'")
            success_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM send_logs")
            total_count = cursor.fetchone()[0]
            
            if total_count > 0:
                success_rate = (success_count / total_count) * 100
                self._update_stat_value(self.success_rate_group, f"{success_rate:.1f}%")
            
            conn.close()
            
        except Exception as e:
            print(f"Error refreshing stats: {e}")
    
    def _update_stat_value(self, group: QGroupBox, value: str):
        """Update the value in a stat box"""
        value_label = group.findChild(QLabel, "value")
        if value_label:
            value_label.setText(value)
