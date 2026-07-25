#!/usr/bin/env python3
"""
Launch script for Outlook Bulk Mail Sender UI
"""
import sys
from PySide6.QtWidgets import QApplication
from loguru import logger

from ui.main_window import MainWindow


def main():
    """Main entry point"""
    # Configure logger
    logger.add("logs/app_{time}.log", rotation="10 MB", level="INFO")
    logger.info("Starting Outlook Bulk Mail Sender application")
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Outlook Bulk Mail Sender")
    app.setOrganizationName("BulkMailSender")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
