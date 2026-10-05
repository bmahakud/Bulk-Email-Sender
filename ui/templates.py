"""
Templates tab - Manage email templates with Subject & Body rotation
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTextEdit, QLabel, QFileDialog, QMessageBox,
                               QLineEdit, QRadioButton, QButtonGroup, QGroupBox,
                               QComboBox, QDialog, QTextBrowser, QCheckBox)
from PySide6.QtCore import Qt
import re
from pathlib import Path
from loguru import logger


class TemplatesTab(QWidget):
    """Templates management tab with multiple body variations, tag reference, and rotation modes"""
    
    def __init__(self):
        super().__init__()
        self.current_html = ""
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Email Content & Templates")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        # Load File button
        load_btn = QPushButton("📂 Load Template File (.txt / .html)")
        load_btn.clicked.connect(self.load_body_file)
        load_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                padding: 8px 18px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)
        header.addWidget(load_btn)
        layout.addLayout(header)
        
        # Rotation Mode Group
        mode_group = QGroupBox("Rotation Mode")
        mode_group.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 5px; }")
        mode_layout = QHBoxLayout(mode_group)
        
        self.mode_btn_group = QButtonGroup(self)
        
        self.radio_per_email = QRadioButton("Per Email (Paired Subject + Body changes every email)")
        self.radio_randomized = QRadioButton("Randomized (Paired Subject + Body picked randomly)")
        self.radio_per_smtp = self.radio_per_email  # backward-compatibility alias
        self.radio_per_email.setChecked(True)
        
        self.mode_btn_group.addButton(self.radio_per_email)
        self.mode_btn_group.addButton(self.radio_randomized)
        
        mode_layout.addWidget(self.radio_per_email)
        mode_layout.addWidget(self.radio_randomized)
        mode_layout.addStretch()
        layout.addWidget(mode_group)
        
        # Subject lines section
        subject_header = QHBoxLayout()
        subject_label = QLabel("Subject Lines (one per line):")
        subject_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        subject_header.addWidget(subject_label)
        subject_header.addStretch()
        
        self.subject_count_label = QLabel("0 subjects loaded")
        self.subject_count_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        subject_header.addWidget(self.subject_count_label)
        layout.addLayout(subject_header)
        
        self.subject_text = QTextEdit()
        self.subject_text.setMaximumHeight(85)
        self.subject_text.setPlaceholderText(
            "Enter subject lines, one per line (each will pair with a body variation)...\n"
            "Example:\n"
            "Thank you for upgrading your subscription\n"
            "Your subscription update is now active\n"
            "Reference information for your account"
        )
        self.subject_text.textChanged.connect(self._update_counts)
        layout.addWidget(self.subject_text)
        
        # Clickable Tag Toolbar
        tag_bar = QHBoxLayout()
        tag_bar_label = QLabel("Click to Insert Tag:")
        tag_bar_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #555;")
        tag_bar.addWidget(tag_bar_label)
        
        quick_tags = ["#EMAIL#", "#NAME#", "#RANDOM#", "#ORDERID#", "#DATE#", "#TIME#", "#COMPANY#"]
        for tag in quick_tags:
            btn = QPushButton(tag)
            btn.setToolTip(f"Click to insert {tag} at cursor position")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #ecf0f1;
                    color: #2c3e50;
                    border: 1px solid #bdc3c7;
                    border-radius: 3px;
                    padding: 3px 8px;
                    font-family: monospace;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #d5dbdb;
                    color: #1a5276;
                }
            """)
            btn.clicked.connect(lambda checked=False, t=tag: self._insert_tag(t))
            tag_bar.addWidget(btn)
            
        tag_bar.addStretch()
        layout.addLayout(tag_bar)
        
        # Body Content Section
        body_header = QHBoxLayout()
        body_label = QLabel("Email Body Content (Separate multiple variations with '===='):")
        body_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        body_header.addWidget(body_label)
        body_header.addStretch()
        
        self.body_count_label = QLabel("0 bodies detected")
        self.body_count_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        body_header.addWidget(self.body_count_label)
        layout.addLayout(body_header)
        
        self.html_text = QTextEdit()
        self.html_text.setPlaceholderText(
            "Paste your email body here (HTML or Plain Text).\n\n"
            "To use MULTIPLE BODY VARIATIONS, separate them with '=====':\n"
            "Dear #EMAIL#,\n"
            "First body message text...\n"
            "Reference: #RANDOM#\n"
            "================================================================\n"
            "Dear #EMAIL#,\n"
            "Second variation text...\n\n"
            "All tags like #EMAIL#, #RANDOM#, #ORDERID# are automatically replaced with real values when sent!"
        )
        self.html_text.textChanged.connect(self._update_counts)
        layout.addWidget(self.html_text)
        
        # Live Tag Detection Display
        self.detected_tags_label = QLabel("🏷️ Detected Tags in Template: None")
        self.detected_tags_label.setStyleSheet("color: #16a085; font-weight: bold; font-size: 12px; margin-top: 2px;")
        layout.addWidget(self.detected_tags_label)
        
        # Action Buttons
        actions_layout = QHBoxLayout()
        
        self.pairs_status_label = QLabel("Ready")
        self.pairs_status_label.setStyleSheet("font-weight: bold; color: #2980b9;")
        actions_layout.addWidget(self.pairs_status_label)
        
        actions_layout.addStretch()
        
        preview_btn = QPushButton("👁️ Preview Body Variations")
        preview_btn.clicked.connect(self.preview_html)
        actions_layout.addWidget(preview_btn)
        
        validate_btn = QPushButton("✓ Validate & Pair")
        validate_btn.clicked.connect(self.validate_template)
        actions_layout.addWidget(validate_btn)
        
        layout.addLayout(actions_layout)
        self._update_counts()

    def _insert_tag(self, tag: str):
        """Insert dynamic tag at current cursor in html_text"""
        cursor = self.html_text.textCursor()
        cursor.insertText(tag)
        self.html_text.setFocus()

    def get_bodies(self) -> list:
        """Extract individual body variations split by ===== divider lines"""
        raw_text = self.html_text.toPlainText().strip()
        if not raw_text:
            return []
        
        # Split by lines containing 5 or more equal signs
        parts = re.split(r'\n\s*={5,}\s*\n?', raw_text)
        cleaned_parts = [p.strip() for p in parts if p.strip()]
        return cleaned_parts if cleaned_parts else [raw_text]

    def get_subjects(self) -> list:
        """Extract subject lines"""
        lines = self.subject_text.toPlainText().strip().split('\n')
        return [s.strip() for s in lines if s.strip()]

    def _update_counts(self):
        """Update live counts of subjects, body variations, and detected tags"""
        subjects = self.get_subjects()
        bodies = self.get_bodies()
        
        self.subject_count_label.setText(f"{len(subjects)} subject(s) loaded")
        self.body_count_label.setText(f"{len(bodies)} body variation(s) detected")
        
        if subjects and bodies:
            pairs = max(len(subjects), len(bodies))
            self.pairs_status_label.setText(f"✓ {pairs} Subject + Body pair(s) configured")
        else:
            self.pairs_status_label.setText("Add subject lines and body text to pair them")
            
        # Detect tags
        combined = ' '.join(subjects) + ' ' + ' '.join(bodies)
        found_tags = sorted(list(set(re.findall(r'#[A-Z_]+#', combined))))
        if found_tags:
            self.detected_tags_label.setText(f"🏷️ Detected Tags in Template: {', '.join(found_tags)}")
        else:
            self.detected_tags_label.setText("🏷️ Detected Tags in Template: None")

    def load_body_file(self):
        """Load template file (.txt or .html) containing single or multiple bodies"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Load Template File",
                "",
                "All Supported (*.txt *.html *.htm);;HTML Files (*.html *.htm);;Text Files (*.txt);;All Files (*.*)"
            )
            
            if not file_path:
                return
            
            logger.info(f"Loading template from {file_path}")
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            self.html_text.setPlainText(content)
            self.current_html = content
            self._update_counts()
            
            bodies = self.get_bodies()
            QMessageBox.information(
                self,
                "Template Loaded",
                f"Successfully loaded '{Path(file_path).name}'\n\n"
                f"Detected {len(bodies)} body variation(s)."
            )
            
        except Exception as e:
            logger.error(f"Error loading template file: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def load_html(self):
        """Backward compatibility alias for load_body_file"""
        return self.load_body_file()

    def preview_html(self):
        """Preview loaded body variations with simulated real tags"""
        from services.tag_engine import TagEngine
        
        bodies = self.get_bodies()
        subjects = self.get_subjects()
        
        if not bodies:
            QMessageBox.warning(self, "Warning", "No email body content to preview")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Email Body Preview ({len(bodies)} Variations)")
        dialog.resize(850, 620)
        
        dialog_layout = QVBoxLayout(dialog)
        
        # Controls bar
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Select Variation:"))
        
        combo = QComboBox()
        for i in range(len(bodies)):
            combo.addItem(f"Variation {i + 1} of {len(bodies)}")
        top_bar.addWidget(combo)
        
        sim_tags_chk = QCheckBox("Preview with Simulated Real Data (replaces #EMAIL#, #RANDOM#, etc.)")
        sim_tags_chk.setChecked(True)
        top_bar.addWidget(sim_tags_chk)
        
        top_bar.addStretch()
        dialog_layout.addLayout(top_bar)
        
        # Subject preview line
        subject_preview_label = QLabel("Subject: -")
        subject_preview_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #2c3e50; padding: 4px; background-color: #ecf0f1; border-radius: 4px;")
        dialog_layout.addWidget(subject_preview_label)
        
        browser = QTextBrowser()
        dialog_layout.addWidget(browser)
        
        sample_recipient = {
            'email': 'alex.smith@example.com',
            'name': 'Alex Smith',
            'orderid': 'ORD-984210',
            'company': 'Global Tech Solutions',
            'invoice': 'INV-2026-001'
        }
        
        def render_current_preview():
            index = combo.currentIndex()
            if 0 <= index < len(bodies):
                body = bodies[index]
                sub = subjects[index % len(subjects)] if subjects else "No Subject Provided"
                
                if sim_tags_chk.isChecked():
                    body = TagEngine.replace_tags(body, sample_recipient)
                    sub = TagEngine.replace_tags(sub, sample_recipient)
                    
                subject_preview_label.setText(f"Subject: {sub}")
                
                # If plain text, wrap newlines to <br> for preview
                if "<html" not in body.lower() and "<div" not in body.lower() and "<p" not in body.lower():
                    preview_content = "<div style='font-family: Arial, Helvetica, sans-serif; font-size: 14px; line-height: 1.6; color: #222;'>" + body.replace("\n", "<br>") + "</div>"
                else:
                    preview_content = body
                browser.setHtml(preview_content)
        
        combo.currentIndexChanged.connect(lambda: render_current_preview())
        sim_tags_chk.stateChanged.connect(lambda: render_current_preview())
        render_current_preview()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        dialog_layout.addWidget(close_btn)
        
        dialog.exec()

    def validate_template(self):
        """Validate template, subjects, and tags"""
        from services.tag_engine import TagEngine
        
        subjects = self.get_subjects()
        bodies = self.get_bodies()
        
        errors = []
        if not subjects:
            errors.append("• No subject lines provided.")
        if not bodies:
            errors.append("• No body content provided.")
            
        if errors:
            QMessageBox.warning(self, "Validation Failed", "\n".join(errors))
            return
        
        # Check tags across all content
        combined_text = ' '.join(subjects) + ' ' + ' '.join(bodies)
        tags = set(TagEngine.find_tags(combined_text))
        
        mode_text = "Randomized (picks random pair)" if self.radio_randomized.isChecked() else "Per Email (rotates every email)"
        
        msg = (
            f"✓ Template Configuration Valid!\n\n"
            f"• Subject Lines: {len(subjects)}\n"
            f"• Body Variations: {len(bodies)}\n"
            f"• Rotation Mode: {mode_text}\n"
        )
        if tags:
            msg += f"• Dynamic Tags Found: {', '.join(sorted(tags))}\n"
            msg += f"  (All tags will be replaced with real recipient values when sent)\n"
        
        if len(subjects) != len(bodies):
            msg += f"\nℹ Note: You have {len(subjects)} subjects and {len(bodies)} bodies. They will rotate cyclically to form {max(len(subjects), len(bodies))} pairs."
            
        QMessageBox.information(self, "Validation Success", msg)

    def get_template_data(self) -> dict:
        """Get template data including multiple bodies and rotation mode"""
        bodies = self.get_bodies()
        subjects = self.get_subjects()
        
        return {
            'html': bodies[0] if bodies else "",
            'bodies': bodies,
            'subjects': subjects,
            'rotation_mode': 'randomized' if self.radio_randomized.isChecked() else 'per_email'
        }
