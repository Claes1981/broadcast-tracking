"""
Broadcast Board Tracking Application

A GUI application to track digital board usage for players/teams in chess tournaments.
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

from gui.main_window import MainWindow
from config import DATA_DIR


def main():
    """Main entry point for the application."""
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Broadcast Board Tracker")
    app.setOrganizationName("ChessTournament")

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
