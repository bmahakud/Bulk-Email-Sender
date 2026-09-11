"""
Unsubscribed Contacts Management Dialog
Provides visual interface to view, search, add, remove, import, and export unsubscribed contacts
with 10-record pagination and an enterprise-grade dark UI.
"""
import csv
import math
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog, QFrame, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from backend.database import Database


class UnsubscribedDialog(QDialog):
    """Modal dialog to view and manage unsubscribed recipient suppression list."""

    PAGE_SIZE = 10

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_page = 1
        self._all_records = []
        self._filtered_records = []

        self.setWindowTitle("Unsubscribed Contacts Management")
        self.setMinimumSize(820, 600)
        self.setStyleSheet("""
            QDialog {
                background: #12131a;
                color: #e8eaf0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #e8eaf0;
            }
            QLineEdit {
                background: #1a1b27;
                color: #e8eaf0;
                border: 1px solid #252637;
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #5865f2;
            }
            QTableWidget {
                background: #161723;
                color: #e8eaf0;
                border: 1px solid #252637;
                gridline-color: #202130;
                border-radius: 6px;
                selection-background-color: #252637;
            }
            QHeaderView::section {
                background: #0d0e17;
                color: #8b92b2;
                padding: 9px 12px;
                font-weight: 600;
                font-size: 11px;
                letter-spacing: 0.5px;
                text-transform: uppercase;
                border: none;
                border-bottom: 1px solid #252637;
            }
        """)

        self._build_ui()
        self._load_data()

        # Non-blocking background sync so dialog opens instantly without freezing
        import threading
        threading.Thread(target=self._background_sync, daemon=True).start()

    def _background_sync(self):
        """Silently sync from cloud in background without freezing the UI."""
        try:
            self._sync_from_cloud(show_msg=False)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._load_data)
        except Exception:
            pass

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 20)
        root.setSpacing(14)

        # ── Header ──
        hdr = QHBoxLayout()
        title = QLabel("Unsubscribed Suppression List")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: #ffffff; letter-spacing: 0.3px;")
        hdr.addWidget(title)

        hdr.addStretch()

        self.lbl_count = QLabel("0 Total Suppressed")
        self.lbl_count.setStyleSheet("""
            background: #252637;
            color: #7289da;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        """)
        hdr.addWidget(self.lbl_count)
        root.addLayout(hdr)

        sub = QLabel("Recipients in this list are automatically excluded and skipped from all sending campaigns.")
        sub.setStyleSheet("color: #7880a0; font-size: 11px;")
        root.addWidget(sub)

        # ── Add Email Bar ──
        add_box = QHBoxLayout()
        add_box.setSpacing(8)

        self.txt_add = QLineEdit()
        self.txt_add.setPlaceholderText("Enter email to suppress (e.g. user@example.com)...")
        self.txt_add.returnPressed.connect(self._add_single_email)
        add_box.addWidget(self.txt_add, 1)

        btn_add = QPushButton("Add Email")
        btn_add.setFixedHeight(34)
        btn_add.setStyleSheet("""
            QPushButton {
                background: #5865f2;
                color: white;
                border: none;
                padding: 0 18px;
                border-radius: 5px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background: #4752c4; }
        """)
        btn_add.clicked.connect(self._add_single_email)
        add_box.addWidget(btn_add)

        btn_import = QPushButton("Import File")
        btn_import.setFixedHeight(34)
        btn_import.setStyleSheet("""
            QPushButton {
                background: #238636;
                color: white;
                border: none;
                padding: 0 16px;
                border-radius: 5px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background: #2ea043; }
        """)
        btn_import.clicked.connect(self._import_from_file)
        add_box.addWidget(btn_import)

        btn_export = QPushButton("Export CSV")
        btn_export.setFixedHeight(34)
        btn_export.setStyleSheet("""
            QPushButton {
                background: #252637;
                color: #e8eaf0;
                border: 1px solid #35374d;
                padding: 0 16px;
                border-radius: 5px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background: #323348; }
        """)
        btn_export.clicked.connect(self._export_to_csv)
        add_box.addWidget(btn_export)

        btn_sync = QPushButton("Sync from Cloud")
        btn_sync.setFixedHeight(34)
        btn_sync.setStyleSheet("""
            QPushButton {
                background: #6c5ce7;
                color: white;
                border: none;
                padding: 0 16px;
                border-radius: 5px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover { background: #5b4bc4; }
        """)
        btn_sync.clicked.connect(lambda: self._sync_from_cloud(show_msg=True))
        add_box.addWidget(btn_sync)

        root.addLayout(add_box)

        # ── Search Bar ──
        search_box = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search email address...")
        self.txt_search.textChanged.connect(self._on_search_changed)
        search_box.addWidget(self.txt_search)
        root.addLayout(search_box)

        # ── Table Widget ──
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Email Address", "Unsubscribed Date & Time", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget { alternate-background-color: #12131b; }
        """)
        root.addWidget(self.table, 1)

        # ── Pagination Bar ──
        pag_box = QHBoxLayout()
        pag_box.setContentsMargins(4, 2, 4, 4)

        self.lbl_page_info = QLabel("Showing 0 to 0 of 0")
        self.lbl_page_info.setStyleSheet("color: #7880a0; font-size: 11px;")
        pag_box.addWidget(self.lbl_page_info)

        pag_box.addStretch()

        self.btn_prev = QPushButton("Previous")
        self.btn_prev.setFixedHeight(28)
        self.btn_prev.setStyleSheet("""
            QPushButton {
                background: #1a1b27;
                color: #e8eaf0;
                border: 1px solid #2e3044;
                padding: 0 14px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover:!disabled { background: #252637; border-color: #5865f2; }
            QPushButton:disabled { color: #47495e; border-color: #202130; background: #14151f; }
        """)
        self.btn_prev.clicked.connect(self._prev_page)
        pag_box.addWidget(self.btn_prev)

        self.lbl_page_num = QLabel("Page 1 of 1")
        self.lbl_page_num.setStyleSheet("color: #e8eaf0; font-size: 12px; font-weight: 600; padding: 0 10px;")
        pag_box.addWidget(self.lbl_page_num)

        self.btn_next = QPushButton("Next")
        self.btn_next.setFixedHeight(28)
        self.btn_next.setStyleSheet("""
            QPushButton {
                background: #1a1b27;
                color: #e8eaf0;
                border: 1px solid #2e3044;
                padding: 0 14px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover:!disabled { background: #252637; border-color: #5865f2; }
            QPushButton:disabled { color: #47495e; border-color: #202130; background: #14151f; }
        """)
        self.btn_next.clicked.connect(self._next_page)
        pag_box.addWidget(self.btn_next)

        root.addLayout(pag_box)

        # ── Bottom Action Bar ──
        bot = QHBoxLayout()

        btn_clear_all = QPushButton("Clear All Suppressions")
        btn_clear_all.setFixedHeight(32)
        btn_clear_all.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #e06c75;
                border: 1px solid #4a2228;
                padding: 0 16px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #ed4245;
                color: white;
                border-color: #ed4245;
            }
        """)
        btn_clear_all.clicked.connect(self._clear_all)
        bot.addWidget(btn_clear_all)

        bot.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(32)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #252637;
                color: #e8eaf0;
                border: 1px solid #35374d;
                padding: 0 24px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #323348; }
        """)
        btn_close.clicked.connect(self.accept)
        bot.addWidget(btn_close)

        root.addLayout(bot)

    def _load_data(self):
        """Fetch all unsubscribed contacts from database and refresh view."""
        self._all_records = self.db.get_unsubscribed_list()
        total = len(self._all_records)
        s = "s" if total != 1 else ""
        self.lbl_count.setText(f"{total} Total Contact{s}")

        # Re-apply current search filter if any
        query = self.txt_search.text().strip().lower()
        if query:
            self._filtered_records = [r for r in self._all_records if query in r.get("email", "").lower()]
        else:
            self._filtered_records = list(self._all_records)

        self._render_current_page()

    def _on_search_changed(self, text: str):
        self.current_page = 1
        query = text.strip().lower()
        if not query:
            self._filtered_records = list(self._all_records)
        else:
            self._filtered_records = [r for r in self._all_records if query in r.get("email", "").lower()]
        self._render_current_page()

    def _render_current_page(self):
        total_items = len(self._filtered_records)
        total_pages = max(1, math.ceil(total_items / self.PAGE_SIZE))

        # Clamp current page
        if self.current_page > total_pages:
            self.current_page = total_pages
        if self.current_page < 1:
            self.current_page = 1

        start_idx = (self.current_page - 1) * self.PAGE_SIZE
        end_idx = min(start_idx + self.PAGE_SIZE, total_items)
        page_items = self._filtered_records[start_idx:end_idx]

        # Update Pagination UI
        if total_items == 0:
            self.lbl_page_info.setText("Showing 0 contacts")
            self.lbl_page_num.setText("Page 1 of 1")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
        else:
            self.lbl_page_info.setText(f"Showing {start_idx + 1}–{end_idx} of {total_items} contacts")
            self.lbl_page_num.setText(f"Page {self.current_page} of {total_pages}")
            self.btn_prev.setEnabled(self.current_page > 1)
            self.btn_next.setEnabled(self.current_page < total_pages)

        # Populate Table
        self.table.setRowCount(0)
        for r in page_items:
            row_idx = self.table.rowCount()
            self.table.insertRow(row_idx)

            # Email
            email_item = QTableWidgetItem(r.get("email", ""))
            email_item.setFlags(email_item.flags() ^ Qt.ItemIsEditable)
            self.table.setItem(row_idx, 0, email_item)

            # Date
            date_str = str(r.get("unsubscribed_at", ""))
            date_item = QTableWidgetItem(date_str)
            date_item.setFlags(date_item.flags() ^ Qt.ItemIsEditable)
            date_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 1, date_item)

            # Action: Remove button
            btn_del = QPushButton("Remove")
            btn_del.setFixedSize(68, 24)
            btn_del.setStyleSheet("""
                QPushButton {
                    background: #252637;
                    color: #e06c75;
                    border: 1px solid #4a2228;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #ed4245;
                    color: white;
                    border-color: #ed4245;
                }
            """)
            target_email = r.get("email", "")
            btn_del.clicked.connect(lambda _, em=target_email: self._remove_email(em))
            self.table.setCellWidget(row_idx, 2, btn_del)

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._render_current_page()

    def _next_page(self):
        total_pages = max(1, math.ceil(len(self._filtered_records) / self.PAGE_SIZE))
        if self.current_page < total_pages:
            self.current_page += 1
            self._render_current_page()

    def _add_single_email(self):
        raw = self.txt_add.text().strip()
        if not raw:
            return
        emails = [e.strip().lower() for e in raw.replace(",", " ").split() if "@" in e]
        if not emails:
            QMessageBox.warning(self, "Invalid Email", "Please enter a valid email address.")
            return

        added_cnt = 0
        for em in emails:
            if self.db.add_unsubscribed(em):
                added_cnt += 1

        self.txt_add.clear()
        self._load_data()
        QMessageBox.information(self, "Contact Added", f"Successfully added {added_cnt} email(s) to the suppression list.")

    def _remove_email(self, email: str):
        reply = QMessageBox.question(
            self, "Confirm Removal",
            f"Remove '{email}' from the suppression list?\n\nThey will become eligible to receive emails again.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM unsubscribed_recipients WHERE LOWER(email) = ?", (email.lower(),))
            conn.commit()
            conn.close()

            # Delete from cloud server as well so future syncs do not re-add it
            try:
                token = self.db.get_setting("license_token", default="")
                lic_key = ""
                if token:
                    from backend.license_validator import verify_token
                    lic_key = verify_token(token).get("license_key", "")
                import requests
                requests.post(
                    "https://promailer-licensing.diracai.com/api/unsubscribed/delete",
                    json={"lic": lic_key, "email": email.strip().lower()},
                    timeout=3
                )
            except Exception:
                pass

            self._load_data()

    def _clear_all(self):
        if not self._all_records:
            return
        reply = QMessageBox.warning(
            self, "Confirm Clear All",
            "Are you sure you want to clear ALL unsubscribed contacts?\n\nThis will remove all suppressed emails permanently.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM unsubscribed_recipients")
            conn.commit()
            conn.close()

            # Clear on cloud server as well
            try:
                token = self.db.get_setting("license_token", default="")
                lic_key = ""
                if token:
                    from backend.license_validator import verify_token
                    lic_key = verify_token(token).get("license_key", "")
                import requests
                requests.post(
                    "https://promailer-licensing.diracai.com/api/unsubscribed/clear",
                    json={"lic": lic_key},
                    timeout=3
                )
            except Exception:
                pass

            self._load_data()
            QMessageBox.information(self, "List Cleared", "All unsubscribed contacts have been cleared.")

    def _import_from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Unsubscribed Emails", "", "Text/CSV Files (*.txt *.csv);;All Files (*)")
        if not path:
            return

        added_cnt = 0
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if "@" in line:
                        parts = line.replace(",", " ").replace(";", " ").split()
                        for p in parts:
                            if "@" in p and "." in p:
                                clean_email = p.strip("<>\"' ")
                                if self.db.add_unsubscribed(clean_email):
                                    added_cnt += 1
            self._load_data()
            QMessageBox.information(self, "Import Complete", f"Successfully imported {added_cnt} unsubscribed email(s).")
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Error reading file: {e}")

    def _export_to_csv(self):
        if not self._all_records:
            QMessageBox.information(self, "Empty List", "The unsubscribed suppression list is currently empty.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export Unsubscribed List", "unsubscribed_contacts.csv", "CSV Files (*.csv)")
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Email Address", "Unsubscribed Date & Time"])
                for r in self._all_records:
                    writer.writerow([r.get("email", ""), r.get("unsubscribed_at", "")])
            QMessageBox.information(self, "Export Complete", f"Exported {len(self._all_records)} contacts to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Error exporting file: {e}")

    def _sync_from_cloud(self, show_msg: bool = False):
        """Fetch unsubscribed recipients from promailer cloud and merge into local database."""
        try:
            token = self.db.get_setting("license_token", default="")
            lic_key = ""
            if token:
                try:
                    from backend.license_validator import verify_token
                    payload = verify_token(token)
                    lic_key = payload.get("license_key", "")
                except Exception:
                    pass
            import requests
            url = "https://promailer-licensing.diracai.com/api/unsubscribed"
            params = {"lic": lic_key} if lic_key else {}
            resp = requests.get(url, params=params, timeout=5)
            if resp.status_code == 200:
                emails = resp.json().get("emails", [])
                added_count = 0
                for item in emails:
                    em = item.get("email", "").strip().lower()
                    if em and self.db.add_unsubscribed(em):
                        added_count += 1
                if show_msg:
                    self._load_data()
                    QMessageBox.information(
                        self, "Cloud Sync Complete",
                        f"Cloud synchronization complete.\n\nTotal records on server: {len(emails)}\nNew records added: {added_count}"
                    )
            elif resp.status_code == 404:
                if show_msg:
                    QMessageBox.information(
                        self, "Cloud Server Update Required",
                        "The web server at promailer-licensing.diracai.com is online, but the new sync endpoint (/api/unsubscribed) has not been uploaded to the server yet.\n\n"
                        "To enable automated cloud sync, upload the updated licensing_server/app.py to your VPS and restart the server.\n\n"
                        "Note: Your local suppression list continues to work normally and skips all suppressed contacts."
                    )
            else:
                if show_msg:
                    QMessageBox.warning(self, "Cloud Sync", f"Server responded with status code: {resp.status_code}")
        except Exception as e:
            if show_msg:
                QMessageBox.warning(self, "Cloud Sync Failed", f"Could not connect to cloud server:\n{e}")

