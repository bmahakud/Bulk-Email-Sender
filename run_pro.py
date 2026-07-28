#!/usr/bin/env python3
"""
ProMailer Pro – Entry Point
Run: python run_pro.py
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor, QFont
from PySide6.QtCore import Qt
from dotenv import load_dotenv

# Load env variables at entry point
load_dotenv(override=True)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ProMailer Pro")
    app.setStyle("Fusion")

    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor(18, 19, 26))
    palette.setColor(QPalette.WindowText,      QColor(232, 234, 240))
    palette.setColor(QPalette.Base,            QColor(26, 27, 39))
    palette.setColor(QPalette.AlternateBase,   QColor(37, 38, 55))
    palette.setColor(QPalette.Text,            QColor(232, 234, 240))
    palette.setColor(QPalette.Button,          QColor(88, 101, 242))
    palette.setColor(QPalette.ButtonText,      QColor(255, 255, 255))
    palette.setColor(QPalette.Highlight,       QColor(88, 101, 242))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ToolTipBase,     QColor(37, 38, 55))
    palette.setColor(QPalette.ToolTipText,     QColor(232, 234, 240))
    app.setPalette(palette)

    app.setFont(QFont("Segoe UI", 11))

    # License and Activation verification
    from backend.license_validator import check_license_status
    status, detail = check_license_status()
    if status != "valid":
        from ui_new.activation_dialog import ActivationDialog
        dlg = ActivationDialog(initial_status_msg=detail)
        dlg.exec()
        if not dlg.activation_successful:
            sys.exit(0)

    from ui_new.main_window import MainWindow
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
