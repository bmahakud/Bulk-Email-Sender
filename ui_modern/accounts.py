"""
Modern Accounts Tab - SMTP Management (DB-integrated)
"""
import csv
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTableWidget, QTableWidgetItem, QLabel, QMessageBox,
                               QTextEdit, QDialog, QGroupBox, QHeaderView, QFrame,
                               QFileDialog)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from backend.database import Database


class AccountsTab(QWidget):
    """SMTP Accounts Management"""

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.init_ui()
        self.load_from_db()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("SMTP Accounts")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        layout.addWidget(title)

        subtitle = QLabel("Manage your email sending accounts")
        subtitle.setStyleSheet("color: #7f8c8d; font-size: 13px; margin-bottom: 15px;")
        layout.addWidget(subtitle)

        # Info box
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #fff;
                border: 1px solid #e8e8e8;
                border-left: 3px solid #5dade2;
                border-radius: 4px;
                padding: 12px 15px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        info_label = QLabel("📋 <b>Format:</b> email|password|token|client_id")
        info_label.setStyleSheet("color: #34495e; font-size: 12px;")
        info_layout.addWidget(info_label)
        layout.addWidget(info_frame)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        btn_add_bulk = QPushButton("+ Add Bulk SMTP")
        btn_add_bulk.setStyleSheet(self.get_button_style("#5dade2"))
        btn_add_bulk.clicked.connect(self.add_bulk_smtp)
        btn_layout.addWidget(btn_add_bulk)

        btn_csv = QPushButton("📁 Import CSV Files")
        btn_csv.setStyleSheet(self.get_button_style("#48c9b0"))
        btn_csv.clicked.connect(self.import_csv_files)
        btn_layout.addWidget(btn_csv)

        btn_test = QPushButton("Test Selected")
        btn_test.setStyleSheet(self.get_button_style("#85929e"))
        btn_test.clicked.connect(self.test_smtp)
        btn_layout.addWidget(btn_test)

        btn_remove = QPushButton("Remove Selected")
        btn_remove.setStyleSheet(self.get_button_style("#ec7063"))
        btn_remove.clicked.connect(self.remove_smtp)
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
        self.stat_total  = self.create_stat_card("Total SMTP",  "0", "#5dade2")
        self.stat_active = self.create_stat_card("Ready",       "0", "#52be80")
        self.stat_failed = self.create_stat_card("Error",       "0", "#ec7063")
        stats_layout.addWidget(self.stat_total)
        stats_layout.addWidget(self.stat_active)
        stats_layout.addWidget(self.stat_failed)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Email", "Password", "Client ID", "Status", "Sent", "Last Used"])
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
            QTableWidget::item { padding: 10px; color: #2c3e50; }
            QTableWidget::item:selected { background-color: #e3f2fd; color: #1976d2; }
        """)
        layout.addWidget(self.table)

    # ── Styling helpers ────────────────────────────────────────────────────────
    def get_button_style(self, color):
        darker = {"#5dade2":"#3498db","#48c9b0":"#16a085","#85929e":"#5d6d7e",
                  "#ec7063":"#e74c3c","#95a5a6":"#7f8c8d","#52be80":"#27ae60"}
        hov = darker.get(color, color)
        return f"""
            QPushButton {{
                background-color: {color}; color: white; border: none;
                padding: 10px 20px; font-size: 13px; font-weight: 500; border-radius: 5px;
            }}
            QPushButton:hover {{ background-color: {hov}; }}
        """

    def create_stat_card(self, title, value, color):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: white; border: 1px solid #e8e8e8;
                border-left: 4px solid {color}; border-radius: 6px;
                padding: 20px; min-width: 160px;
            }}
        """)
        lay = QVBoxLayout(frame)
        lay.setSpacing(8)
        t = QLabel(title);  t.setStyleSheet("color:#7f8c8d; font-size:11px; font-weight:500;")
        v = QLabel(value);  v.setFont(QFont("Segoe UI", 26, QFont.Bold))
        v.setStyleSheet(f"color:{color};")
        v.setObjectName(f"stat_{title.lower().replace(' ','_')}")
        lay.addWidget(t); lay.addWidget(v)
        return frame

    def _stat_label(self, frame, name):
        return frame.findChild(QLabel, f"stat_{name.lower().replace(' ','_')}")

    # ── DB helpers ─────────────────────────────────────────────────────────────
    def load_from_db(self):
        """Reload table from SQLite."""
        self.table.setRowCount(0)
        accounts = self.db.get_smtp_accounts()
        for acc in accounts:
            self._add_row(acc['email'], acc.get('password',''), acc.get('client_id',''),
                          acc.get('token',''), acc.get('status','ready'),
                          str(acc.get('emails_sent', 0)),
                          str(acc.get('last_used','Never') or 'Never'))
        self.update_stats()

    def _add_row(self, email, password, client_id, token, status='ready', sent='0', last_used='Never'):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(email))
        self.table.setItem(row, 1, QTableWidgetItem(password))
        self.table.setItem(row, 2, QTableWidgetItem(client_id))
        color = "#52be80" if status == 'ready' else "#ec7063"
        status_item = QTableWidgetItem(f"● {status.title()}")
        status_item.setForeground(QColor(color))
        self.table.setItem(row, 3, status_item)
        self.table.setItem(row, 4, QTableWidgetItem(sent))
        self.table.setItem(row, 5, QTableWidgetItem(last_used))

    def _save_account(self, email, password, token, client_id):
        """Persist to DB."""
        try:
            self.db.add_smtp_account(email, password, token, client_id)
        except Exception as e:
            pass  # Duplicate handled inside

    # ── Bulk add dialog ────────────────────────────────────────────────────────
    def add_bulk_smtp(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Bulk SMTP Accounts")
        dialog.setMinimumSize(650, 450)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(25, 25, 25, 25)

        label = QLabel("Paste SMTP accounts (one per line)")
        label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        layout.addWidget(label)

        fmt = QLabel("Format: email|password|token|client_id")
        fmt.setStyleSheet("color: #7f8c8d; font-size: 12px; margin-bottom: 10px;")
        layout.addWidget(fmt)

        text_edit = QTextEdit()
        text_edit.setPlaceholderText("user@outlook.com|Password1|oauth_token|client-id-uuid")
        text_edit.setStyleSheet("""
            QTextEdit { border:1px solid #d0d0d0; border-radius:5px; padding:12px;
                        font-family:'Consolas',monospace; font-size:12px; background-color:white; }
        """)
        layout.addWidget(text_edit)

        btn_lay = QHBoxLayout()
        btn_lay.addStretch()
        btn_cancel = QPushButton("Cancel"); btn_cancel.setStyleSheet(self.get_button_style("#95a5a6"))
        btn_cancel.clicked.connect(dialog.reject)
        btn_add = QPushButton("✓ Add Accounts"); btn_add.setStyleSheet(self.get_button_style("#52be80"))
        btn_add.clicked.connect(lambda: self.process_bulk_smtp(text_edit.toPlainText(), dialog))
        btn_lay.addWidget(btn_cancel); btn_lay.addWidget(btn_add)
        layout.addLayout(btn_lay)
        dialog.exec()

    def process_bulk_smtp(self, text, dialog):
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        added = 0
        for line in lines:
            parts = line.split('|')
            if len(parts) >= 4:
                email, password, token, client_id = parts[0], parts[1], parts[2], parts[3]
                self._save_account(email.strip(), password.strip(), token.strip(), client_id.strip())
                added += 1
        self.load_from_db()
        QMessageBox.information(self, "Success", f"Added {added} SMTP accounts!")
        dialog.accept()

    def import_csv_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Import CSV Files", "", "CSV Files (*.csv);;All Files (*)")
        if not file_paths:
            return
        total_added = 0
        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if len(row) >= 4:
                            email, password, token, client_id = [r.strip() for r in row[:4]]
                            if email and password:
                                self._save_account(email, password, token, client_id)
                                total_added += 1
            except Exception as e:
                QMessageBox.warning(self, "Import Error", f"{file_path}: {e}")
        self.load_from_db()
        QMessageBox.information(self, "Import Complete", f"Imported {total_added} SMTP accounts.")

    # ── Actions ────────────────────────────────────────────────────────────────
    def test_smtp(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "No Selection", "Select SMTP accounts to test first.")
            return
        for index in rows:
            row = index.row()
            token     = self.table.item(row, 2).text()
            si        = self.table.item(row, 3)
            si.setText("● Tested"); si.setForeground(QColor("#52be80"))
        QMessageBox.information(self, "Test", f"Tested {len(rows)} account(s). (Token check not yet wired.)") 

    def remove_smtp(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "None Selected", "Select rows to remove.")
            return
        emails = [self.table.item(r.row(), 0).text() for r in rows]
        for email in emails:
            conn = self.db.get_connection()
            conn.execute("DELETE FROM smtp_accounts WHERE email=?", (email,))
            conn.commit(); conn.close()
        self.load_from_db()

    def clear_all(self):
        if QMessageBox.question(self, "Confirm", "Clear ALL SMTP accounts from database?",
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            conn = self.db.get_connection()
            conn.execute("DELETE FROM smtp_accounts"); conn.commit(); conn.close()
            self.load_from_db()

    # ── Stats ──────────────────────────────────────────────────────────────────
    def update_stats(self):
        total = self.table.rowCount()
        active = sum(1 for r in range(total)
                     if self.table.item(r, 3) and 'Ready' in self.table.item(r, 3).text())
        failed = total - active
        lbl = self._stat_label(self.stat_total,  "total_smtp")
        if lbl: lbl.setText(str(total))
        lbl = self._stat_label(self.stat_active, "ready")
        if lbl: lbl.setText(str(active))
        lbl = self._stat_label(self.stat_failed, "error")
        if lbl: lbl.setText(str(failed))

    def get_accounts(self):
        """Return list of accounts dicts for use by sender."""
        return self.db.get_smtp_accounts(status='ready')
