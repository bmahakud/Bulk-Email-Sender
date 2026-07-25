"""
Recipients tab - Import and manage email recipients
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QLabel, QFileDialog,
                               QMessageBox)
from PySide6.QtCore import Qt
import pandas as pd
from loguru import logger

from database.models import Recipient


class RecipientsTab(QWidget):
    """Recipients management tab"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Recipients")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        # Import button
        import_btn = QPushButton("📥 Import CSV/Excel")
        import_btn.clicked.connect(self.import_recipients)
        import_btn.setStyleSheet("""
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
        header.addWidget(import_btn)
        
        # Clear button
        clear_btn = QPushButton("🗑️ Clear All")
        clear_btn.clicked.connect(self.clear_recipients)
        header.addWidget(clear_btn)
        
        layout.addLayout(header)
        
        # Info label
        info = QLabel("Import CSV/Excel with columns: email, name, company, invoice")
        info.setStyleSheet("color: #7f8c8d; padding: 5px;")
        layout.addWidget(info)
        
        # Recipients table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Email", "Name", "Company", "Invoice", "Status"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)
        
        # Count label
        self.count_label = QLabel("Total: 0 recipients")
        self.count_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.count_label)
    
    def import_recipients(self):
        """Import recipients from CSV or Excel"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Import Recipients",
                "",
                "CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*.*)"
            )
            
            if not file_path:
                return
            
            logger.info(f"Importing recipients from {file_path}")
            
            # Read file
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            # Validate columns
            required_cols = ['email']
            if not all(col in df.columns for col in required_cols):
                QMessageBox.warning(
                    self,
                    "Invalid File",
                    "File must contain at least an 'email' column"
                )
                return
            
            # Clean data
            df = df.fillna('')
            df = df.drop_duplicates(subset=['email'])
            
            # Validate emails (basic)
            invalid_emails = df[~df['email'].str.contains('@')]['email'].tolist()
            if invalid_emails:
                QMessageBox.warning(
                    self,
                    "Invalid Emails",
                    f"Found {len(invalid_emails)} invalid email addresses. They will be skipped."
                )
                df = df[df['email'].str.contains('@')]
            
            # Convert to dict list
            recipients = df.to_dict('records')
            
            # Insert into database
            Recipient.bulk_insert(recipients)
            
            QMessageBox.information(
                self,
                "Success",
                f"Imported {len(recipients)} recipients successfully!"
            )
            
            logger.info(f"Imported {len(recipients)} recipients")
            self.load_recipients()
            
        except Exception as e:
            logger.error(f"Error importing recipients: {e}")
            QMessageBox.critical(self, "Error", f"Failed to import: {str(e)}")
    
    def load_recipients(self):
        """Load and display recipients"""
        try:
            from database.models import get_connection
            
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recipients ORDER BY id DESC LIMIT 1000")
            recipients = cursor.fetchall()
            conn.close()
            
            self.table.setRowCount(len(recipients))
            
            for row, recipient in enumerate(recipients):
                self.table.setItem(row, 0, QTableWidgetItem(recipient['email']))
                self.table.setItem(row, 1, QTableWidgetItem(recipient['name'] or ''))
                self.table.setItem(row, 2, QTableWidgetItem(recipient['company'] or ''))
                self.table.setItem(row, 3, QTableWidgetItem(recipient['invoice'] or ''))
                self.table.setItem(row, 4, QTableWidgetItem(recipient['status']))
            
            self.table.resizeColumnsToContents()
            self.count_label.setText(f"Total: {len(recipients)} recipients (showing last 1000)")
            
        except Exception as e:
            logger.error(f"Error loading recipients: {e}")
    
    def clear_recipients(self):
        """Clear all recipients"""
        reply = QMessageBox.question(
            self,
            "Confirm Clear",
            "Are you sure you want to delete all recipients?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                from database.models import get_connection
                
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM recipients")
                conn.commit()
                conn.close()
                
                self.load_recipients()
                QMessageBox.information(self, "Success", "All recipients cleared")
                
            except Exception as e:
                logger.error(f"Error clearing recipients: {e}")
                QMessageBox.critical(self, "Error", str(e))
