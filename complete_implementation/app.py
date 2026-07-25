"""
Outlook Bulk Mail Sender
Main application entry point
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from dotenv import load_dotenv
from loguru import logger

from ui.main_window import MainWindow
from database.models import init_database

# Load environment variables
load_dotenv()

# Configure logger
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)


def main():
    """Main application entry point"""
    logger.info("Starting Outlook Bulk Mail Sender")
    
    # Initialize database
    init_database()
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Outlook Mail Sender")
    app.setOrganizationName("BulkMailer")
    
    # Set high DPI support
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
