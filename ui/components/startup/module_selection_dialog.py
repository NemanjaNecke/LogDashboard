# ui/components/startup/module_selection_dialog.py

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox,
    QPushButton, QLabel
)


class ModuleSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Modules")

        self.iis_checkbox = QCheckBox("IIS")
        self.evtx_checkbox = QCheckBox("EVTX")
        self.generic_checkbox = QCheckBox("Generic")

        # Lay out checkboxes
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Select which modules you want to load:"))
        layout.addWidget(self.iis_checkbox)
        layout.addWidget(self.evtx_checkbox)
        layout.addWidget(self.generic_checkbox)

        # Add OK/Cancel buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Connect signals
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

    def get_selected_modules(self):
        """
        Return a set/list of modules the user checked.
        """
        selected = []
        if self.iis_checkbox.isChecked():
            selected.append("IIS")
        if self.evtx_checkbox.isChecked():
            selected.append("EVTX")
        if self.generic_checkbox.isChecked():
            selected.append("GENERIC")

        return selected
