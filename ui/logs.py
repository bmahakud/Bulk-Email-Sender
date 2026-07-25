"""
Logs tab - View send logs and export
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QLabel, QFileDialog,
                               QMessageBox, QComboBox)
from PySide6.QtCore import Qt
import csv
from datetime import datetime
from loguru import logger

from database.models import get_connection


class LogsTab(QWidget):
    """Logs viewing tab"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Send Logs")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        # Filter
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Success", "Failed"])
        self.filter_combo.currentTextChanged.connect(self.load_logs)
        header.addWidget(QLabel("Filter:"))
        header.addWidget(self.filter_combo)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.load_logs)
        header.addWidget(refresh_btn)
        
        # Export button
        export_btn = QPushButton("📥 Export CSV")
        export_btn.clicked.connect(self.export_logs)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #16a085;
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #138d75;
            }
        """)
        header.addWidget(export_btn)
        
        layout.addLayout(header)
        
        # Logs table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Time", "Recipient", "Account", "Subject", "Status", "Response Code", "Error"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)
        
        # Count label
        self.count_label = QLabel("Total: 0 logs")
        self.count_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.count_label)
        
        # Load logs
        self.load_logs()
    
    def load_logs(self):
        """Load and display logs"""
        try:
            filter_status = self.filter_combo.currentText().lower()
            
            conn = get_connection()
            cursor = conn.cursor()
            
            if filter_status == "all":
                cursor.execute("""
                    SELECT * FROM send_logs 
                    ORDER BY sent_at DESC 
                    LIMIT 1000
                """)
            else:
                cursor.execute("""
                    SELECT * FROM send_logs 
                    WHERE status = ?
                    ORDER BY sent_at DESC 
                    LIMIT 1000
                """, (filter_status,))
            
            logs = cursor.fetchall()
            conn.close()
            
            self.table.setRowCount(len(logs))
            
            for row, log in enumerate(logs):
                # Time
                self.table.setItem(row, 0, QTableWidgetItem(str(log['sent_at'])))
                
                # Recipient
                self.table.setItem(row, 1, QTableWidgetItem(log['recipient_email']))
                
                # Account
                self.table.setItem(row, 2, QTableWidgetItem(log['account_email']))
                
                # Subject
                self.table.setItem(row, 3, QTableWidgetItem(log['subject'] or ''))
                
                # Status
                status_item = QTableWidgetItem(log['status'])
                if log['status'] == 'success':
                    status_item.setForeground(Qt.green)
                else:
                    status_item.setForeground(Qt.red)
                self.table.setItem(row, 4, status_item)
                
                # Response code
                self.table.setItem(row, 5, QTableWidgetItem(str(log['response_code'] or '')))
                
                # Error
                self.table.setItem(row, 6, QTableWidgetItem(log['error_message'] or ''))
            
            self.table.resizeColumnsToContents()
            self.count_label.setText(f"Total: {len(logs)} logs (showing last 1000)")
            
        except Exception as e:
            logger.error(f"Error loading logs: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load logs: {str(e)}")
    
    def export_logs(self):
        """Export logs to CSV"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Logs",
                f"logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv)"
            )
            
            if not file_path:
                return
            
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM send_logs ORDER BY sent_at DESC")
            logs = cursor.fetchall()
            conn.close()
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Time', 'Campaign ID', 'Recipient', 'Account', 'Subject',
                    'Status', 'Response Code', 'Error Message', 'Retry Count'
                ])
                
                for log in logs:
                    writer.writerow([
                        log['sent_at'],
                        log['campaign_id'],
                        log['recipient_email'],
                        log['account_email'],
                        log['subject'],
                        log['status'],
                        log['response_code'],
                        log['error_message'],
                        log['retry_count']
                    ])
            
            QMessageBox.information(
                self,
                "Success",
                f"Exported {len(logs)} logs to:\n{file_path}"
            )
            
            logger.info(f"Exported {len(logs)} logs to {file_path}")
            
        except Exception as e:
            logger.error(f"Error exporting logs: {e}")
            QMessageBox.critical(self, "Error", f"Failed to export logs: {str(e)}")
