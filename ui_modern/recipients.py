"""
Modern Recipients Tab - Email Data Management (DB-integrated)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QLabel, QMessageBox,
                               QTextEdit, QDialog, QFileDialog, QHeaderView, QFrame,
                               QProgressBar)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
import csv

from backend.database import Database


class RecipientsTab(QWidget):
    """Email Recipients Management"""
    
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.recipients = []
        self.init_ui()
        self.load_from_db()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QLabel("Email Recipients")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        layout.addWidget(title)
        
        subtitle = QLabel("Import and manage your email recipients")
        subtitle.setStyleSheet("color: #7f8c8d; font-size: 13px; margin-bottom: 15px;")
        layout.addWidget(subtitle)
        
        # Info box
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border: 1px solid #e8e8e8;
                border-left: 3px solid #a29bfe;
                border-radius: 4px;
                padding: 12px 15px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        info_label = QLabel("📋 <b>Supported:</b> CSV/Excel files (Email, Name) or direct copy-paste")
        info_label.setStyleSheet("color: #34495e; font-size: 12px;")
        info_layout.addWidget(info_label)
        layout.addWidget(info_frame)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        btn_csv = QPushButton("📁 Import CSV/Excel Files")
        btn_csv.setStyleSheet(self.get_button_style("#a29bfe"))
        btn_csv.clicked.connect(self.import_csv)
        btn_layout.addWidget(btn_csv)
        
        btn_paste = QPushButton("+ Copy & Paste")
        btn_paste.setStyleSheet(self.get_button_style("#74b9ff"))
        btn_paste.clicked.connect(self.paste_emails)
        btn_layout.addWidget(btn_paste)
        
        btn_remove = QPushButton("Remove Selected")
        btn_remove.setStyleSheet(self.get_button_style("#ec7063"))
        btn_remove.clicked.connect(self.remove_selected)
        btn_layout.addWidget(btn_remove)
        
        btn_clear = QPushButton("Clear All")
        btn_clear.setStyleSheet(self.get_button_style("#95a5a6"))
        btn_clear.clicked.connect(self.clear_all)
        btn_layout.addWidget(btn_clear)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Stats
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(15)
        self.stat_total = self.create_stat_card("Total", "0", "#a29bfe")
        self.stat_pending = self.create_stat_card("Pending", "0", "#fdcb6e")
        self.stat_sent = self.create_stat_card("Sent", "0", "#55efc4")
        self.stat_remaining = self.create_stat_card("Remaining", "0", "#74b9ff")
        stats_layout.addWidget(self.stat_total)
        stats_layout.addWidget(self.stat_pending)
        stats_layout.addWidget(self.stat_sent)
        stats_layout.addWidget(self.stat_remaining)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Email", "Name", "Status", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background-color: white;
                gridline-color: #f0f0f0;
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
                padding: 10px;
                color: #2c3e50;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
        """)
        layout.addWidget(self.table)
    
    def get_button_style(self, color):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                opacity: 0.85;
            }}
            QPushButton:pressed {{
                padding: 11px 19px 9px 21px;
            }}
        """
    
    def create_stat_card(self, title, value, color):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid #e8e8e8;
                border-left: 4px solid {color};
                border-radius: 6px;
                padding: 20px;
                min-width: 140px;
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(8)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: 500;")
        title_label.setAlignment(Qt.AlignLeft)
        
        value_label = QLabel(value)
        value_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        value_label.setStyleSheet(f"color: {color};")
        value_label.setAlignment(Qt.AlignLeft)
        value_label.setObjectName(f"stat_{title.lower().replace(' ', '_')}")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return frame
    
    def import_csv(self):
        """Import multiple CSV/Excel files"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Import CSV/Excel Files", "", 
            "CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        
        if not file_paths:
            return
        
        total_added = 0
        errors = []
        
        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    next(reader, None)  # Skip header
                    
                    for row_num, row in enumerate(reader, 1):
                        try:
                            if len(row) >= 1:
                                email = row[0].strip()
                                name = row[1].strip() if len(row) > 1 else ""
                                if email:
                                    self.add_recipient(email, name)
                                    total_added += 1
                        except Exception as e:
                            errors.append(f"{file_path} (row {row_num}): {str(e)}")
            
            except Exception as e:
                errors.append(f"{file_path}: {str(e)}")
        
        self.update_stats()
        
        msg = f"Successfully imported {total_added} recipients from {len(file_paths)} file(s)!"
        if errors:
            msg += f"\n\nErrors: {len(errors)}"
            for err in errors[:5]:
                msg += f"\n• {err}"
        
        QMessageBox.information(self, "Import Complete", msg)
    
    def paste_emails(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Copy & Paste Email Data")
        dialog.setMinimumSize(650, 450)
        dialog.setStyleSheet("QDialog { background-color: #f5f6fa; }")
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(25, 25, 25, 25)
        
        label = QLabel("Paste email data (one per line)")
        label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        label.setStyleSheet("color: #2c3e50; margin-bottom: 8px;")
        layout.addWidget(label)
        
        format_label = QLabel("Format: email, name (or just email)")
        format_label.setStyleSheet("color: #7f8c8d; font-size: 12px; margin-bottom: 10px;")
        layout.addWidget(format_label)
        
        text_edit = QTextEdit()
        text_edit.setPlaceholderText("example1@email.com, John Doe\nexample2@email.com, Jane Smith\nexample3@email.com")
        text_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d0d0d0;
                border-radius: 5px;
                padding: 12px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                background-color: white;
            }
            QTextEdit:focus {
                border: 1px solid #a29bfe;
            }
        """)
        layout.addWidget(text_edit)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        btn_add = QPushButton("✓ Add Recipients")
        btn_add.setStyleSheet(self.get_button_style("#55efc4"))
        btn_add.clicked.connect(lambda: self.process_paste(text_edit.toPlainText(), dialog))
        
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet(self.get_button_style("#95a5a6"))
        btn_cancel.clicked.connect(dialog.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_add)
        layout.addLayout(btn_layout)
        
        dialog.exec()
    
    def process_paste(self, text, dialog):
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        added = 0
        
        for line in lines:
            if ',' in line:
                parts = line.split(',', 1)
                email = parts[0].strip()
                name = parts[1].strip() if len(parts) > 1 else ""
            else:
                email = line.strip()
                name = ""
            
            if email:
                self.add_recipient(email, name)
                added += 1
        
        self.update_stats()
        QMessageBox.information(self, "Success", f"Added {added} recipients!")
        dialog.accept()
    
    def load_from_db(self):
        """Reload table from SQLite."""
        self.table.setRowCount(0)
        self.recipients = []
        for rec in self.db.get_recipients():
            self._add_row(rec['email'], rec.get('name','') or '', rec.get('status','pending'))
        self.update_stats()

    def add_recipient(self, email, name=""):
        """Save to DB then show in table."""
        try:
            self.db.add_recipient(email, name)
        except Exception:
            pass
        self._add_row(email, name, 'pending')
        self.recipients.append({'email': email, 'name': name, 'status': 'pending'})

    def _add_row(self, email, name, status):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(email))
        self.table.setItem(row, 1, QTableWidgetItem(name))
        color = '#fdcb6e' if status == 'pending' else ('#55efc4' if status == 'sent' else '#ec7063')
        si = QTableWidgetItem(f"● {status.title()}"); si.setForeground(QColor(color))
        self.table.setItem(row, 2, si)
        btn = QPushButton("×"); btn.setStyleSheet(self.get_button_style("#ec7063")); btn.setMaximumWidth(40)
        btn.clicked.connect(lambda checked, r=row: self.table.removeRow(r))
        self.table.setCellWidget(row, 3, btn)
    
    def remove_selected(self):
        selected_rows = self.table.selectionModel().selectedRows()
        for index in sorted(selected_rows, reverse=True):
            email_item = self.table.item(index.row(), 0)
            if email_item:
                conn = self.db.get_connection()
                conn.execute('DELETE FROM recipients WHERE email=?', (email_item.text(),))
                conn.commit(); conn.close()
            self.table.removeRow(index.row())
        self.update_stats()
    
    def clear_all(self):
        if QMessageBox.question(self, "Confirm", "Clear ALL recipients from database?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            conn = self.db.get_connection()
            conn.execute('DELETE FROM recipients'); conn.commit(); conn.close()
            self.table.setRowCount(0)
            self.recipients.clear()
            self.update_stats()
    
    def update_stats(self):
        total   = self.table.rowCount()
        pending = sum(1 for i in range(total)
                      if self.table.item(i,2) and 'Pending' in self.table.item(i,2).text())
        sent    = sum(1 for i in range(total)
                      if self.table.item(i,2) and 'Sent'    in self.table.item(i,2).text())
        def _set(frame, name, val):
            lbl = frame.findChild(QLabel, name)
            if lbl: lbl.setText(str(val))
        _set(self.stat_total,     'stat_total',     total)
        _set(self.stat_pending,   'stat_pending',   pending)
        _set(self.stat_sent,      'stat_sent',      sent)
        _set(self.stat_remaining, 'stat_remaining', pending)
