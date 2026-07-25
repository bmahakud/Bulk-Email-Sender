"""
Templates tab - Manage email templates
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QTextEdit, QLabel, QFileDialog, QMessageBox,
                               QLineEdit)
from PySide6.QtCore import Qt
from pathlib import Path
from loguru import logger


class TemplatesTab(QWidget):
    """Templates management tab"""
    
    def __init__(self):
        super().__init__()
        self.current_html = ""
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Email Templates")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        
        # Load HTML button
        load_btn = QPushButton("📂 Load HTML File")
        load_btn.clicked.connect(self.load_html)
        load_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)
        header.addWidget(load_btn)
        
        layout.addLayout(header)
        
        # Subject lines section
        subject_layout = QVBoxLayout()
        subject_label = QLabel("Subject Lines (one per line for rotation):")
        subject_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        subject_layout.addWidget(subject_label)
        
        self.subject_text = QTextEdit()
        self.subject_text.setMaximumHeight(100)
        self.subject_text.setPlaceholderText("Enter subject lines, one per line...\nExample:\nInvoice Ready\nYour Payment\nDownload Invoice")
        subject_layout.addWidget(self.subject_text)
        
        layout.addLayout(subject_layout)
        
        # HTML content
        html_label = QLabel("HTML Content:")
        html_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(html_label)
        
        self.html_text = QTextEdit()
        self.html_text.setPlaceholderText("HTML content will appear here...\n\nYou can use tags like:\n#EMAIL# - Recipient email\n#NAME# - Recipient name\n#COMPANY# - Company name\n#INVOICE# - Invoice number\n#DATE# - Current date")
        layout.addWidget(self.html_text)
        
        # Preview button
        preview_layout = QHBoxLayout()
        preview_layout.addStretch()
        
        preview_btn = QPushButton("👁️ Preview HTML")
        preview_btn.clicked.connect(self.preview_html)
        preview_layout.addWidget(preview_btn)
        
        validate_btn = QPushButton("✓ Validate")
        validate_btn.clicked.connect(self.validate_template)
        preview_layout.addWidget(validate_btn)
        
        layout.addLayout(preview_layout)
    
    def load_html(self):
        """Load HTML file"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Load HTML Template",
                "",
                "HTML Files (*.html *.htm);;All Files (*.*)"
            )
            
            if not file_path:
                return
            
            logger.info(f"Loading HTML template from {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            self.html_text.setPlainText(html_content)
            self.current_html = html_content
            
            QMessageBox.information(
                self,
                "Success",
                f"Loaded HTML template: {Path(file_path).name}"
            )
            
        except Exception as e:
            logger.error(f"Error loading HTML: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load HTML: {str(e)}")
    
    def preview_html(self):
        """Preview HTML in dialog"""
        from PySide6.QtWidgets import QDialog, QTextBrowser
        
        html = self.html_text.toPlainText()
        
        if not html:
            QMessageBox.warning(self, "Warning", "No HTML content to preview")
            return
        
        # Create preview dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("HTML Preview")
        dialog.resize(800, 600)
        
        layout = QVBoxLayout(dialog)
        
        browser = QTextBrowser()
        browser.setHtml(html)
        layout.addWidget(browser)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    def validate_template(self):
        """Validate template"""
        from services.html_parser import HTMLParser
        from services.tag_engine import TagEngine
        
        html = self.html_text.toPlainText()
        subjects = self.subject_text.toPlainText().strip().split('\n')
        subjects = [s.strip() for s in subjects if s.strip()]
        
        errors = []
        
        # Validate HTML
        if not html:
            errors.append("HTML content is empty")
        else:
            is_valid, error = HTMLParser.validate_html(html)
            if not is_valid:
                errors.append(f"HTML validation failed: {error}")
        
        # Validate subjects
        if not subjects:
            errors.append("No subject lines provided")
        
        # Check for tags
        tags = TagEngine.find_tags(html + ' '.join(subjects))
        
        if errors:
            QMessageBox.warning(
                self,
                "Validation Failed",
                "\n".join(errors)
            )
        else:
            msg = "✓ Template is valid!\n\n"
            if tags:
                msg += f"Found tags: {', '.join(set(tags))}"
            QMessageBox.information(self, "Validation Success", msg)
    
    def get_template_data(self) -> dict:
        """Get current template data"""
        return {
            'html': self.html_text.toPlainText(),
            'subjects': [s.strip() for s in self.subject_text.toPlainText().split('\n') if s.strip()]
        }
