# main.py

import sys
import logging

from PyQt5.QtWidgets import QApplication
import qdarkstyle

from logdashboard.services.logging.logging_config import setup_logging

# Import your newly created ModuleSelectionDialog
from logdashboard.ui.components.startup.module_selection_dialog import ModuleSelectionDialog

# Import MainWindow last (because it’s big)
from logdashboard.ui.main_window import MainWindow


def main():
    setup_logging()
    logger = logging.getLogger('Main')
    logger.info("Starting Log Dashboard application.")

    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())  # Apply dark theme

    # 1. Show the module selection dialog
    selection_dialog = ModuleSelectionDialog()
    if selection_dialog.exec_() == 0:
        # User canceled
        logger.info("User canceled module selection. Exiting.")
        sys.exit(0)

    selected_modules = selection_dialog.get_selected_modules()
    logger.info(f"User selected modules: {selected_modules}")

    # 2. Pass the modules into MainWindow
    window = MainWindow(selected_modules=selected_modules)
    window.show()
    logger.debug("MainWindow displayed.")
    exit_code = app.exec_()
    logger.info(f"Log Dashboard application exited with code: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()