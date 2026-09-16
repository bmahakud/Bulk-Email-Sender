#!/usr/bin/env python3
"""
ProMailer Pro – Entry Point
Run: python run_pro.py
"""
import os
import sys
import PySide6

# Configure Windows DLL directories for PySide6 (handles both frozen EXE and Anaconda)
if sys.platform == "win32":
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        for d in [meipass, os.path.join(meipass, "PySide6"), os.path.join(meipass, "shiboken6")]:
            if os.path.exists(d) and hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(d)
                except Exception:
                    pass
    else:
        pyside_dir = os.path.dirname(PySide6.__file__)
        for sub in [os.path.join("plugins", "platforms"), os.path.join("Qt", "plugins", "platforms")]:
            candidate = os.path.join(pyside_dir, sub)
            if os.path.exists(candidate):
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = candidate
                break

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
    w.showMaximized()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
