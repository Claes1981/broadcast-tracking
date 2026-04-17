from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFormLayout,
    QComboBox,
    QMessageBox,
    QFileDialog,
    QSpinBox,
)
from PyQt6.QtCore import Qt


class NewTournamentDialog(QDialog):
    """Dialog for creating a new tournament."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Tournament")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Enter tournament name")
        form_layout.addRow("Tournament Name:", name_edit)

        url_edit = QLineEdit()
        url_edit.setPlaceholderText(
            "https://member.schack.se/ShowTournamentServlet?id=XXXXX"
        )
        form_layout.addRow("Source URL (optional):", url_edit)

        type_combo = QComboBox()
        type_combo.addItems(["individual", "team"])
        form_layout.addRow("Tournament Type:", type_combo)

        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        create_btn = QPushButton("Create")
        create_btn.setDefault(True)
        create_btn.clicked.connect(lambda: self.accept() if name_edit.text() else None)
        button_layout.addWidget(create_btn)

        layout.addLayout(button_layout)

        self._name_edit = name_edit
        self._url_edit = url_edit
        self._type_combo = type_combo

    def get_data(self) -> tuple[str, str, str]:
        return (
            self._name_edit.text().strip(),
            self._url_edit.text().strip(),
            self._type_combo.currentText(),
        )


class FetchPairingsDialog(QDialog):
    """Dialog for fetching pairings from URL."""

    def __init__(self, parent=None, existing_url: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Fetch Pairings")
        self.setMinimumWidth(400)
        self._setup_ui(existing_url)

    def _setup_ui(self, existing_url: str):
        layout = QVBoxLayout(self)

        info_label = QLabel(
            "Enter the tournament URL to fetch available rounds.\n"
            "Example: https://member.schack.se/ShowTournamentServlet?id=16441"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        url_edit = QLineEdit(existing_url)
        url_edit.setPlaceholderText(
            "https://member.schack.se/ShowTournamentServlet?id=XXXXX"
        )
        layout.addWidget(url_edit)

        self._rounds_list = []
        self._rounds_label = QLabel("Available rounds will appear here...")
        layout.addWidget(self._rounds_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        fetch_btn = QPushButton("Fetch Rounds")
        fetch_btn.clicked.connect(lambda: self._on_fetch(url_edit))
        button_layout.addWidget(fetch_btn)

        layout.addLayout(button_layout)

        self._url_edit = url_edit

    def _on_fetch(self, url_edit: QLineEdit):
        url = url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a URL")
            return

        self._rounds_label.setText("Fetching...")
        self._rounds_list = []
        self.accept()

    def get_url(self) -> str:
        return self._url_edit.text().strip()

    def set_available_rounds(self, rounds: list[int]):
        self._rounds_list = rounds
        if rounds:
            self._rounds_label.setText(
                f"Available rounds: {', '.join(map(str, rounds))}"
            )
        else:
            self._rounds_label.setText("No rounds found")


class SettingsDialog(QDialog):
    """Dialog for tournament settings."""

    def __init__(self, parent=None, num_digital_boards: int = 5):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(300)
        self._setup_ui(num_digital_boards)

    def _setup_ui(self, num_digital_boards: int):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        boards_spin = QSpinBox()
        boards_spin.setRange(1, 100)
        boards_spin.setValue(num_digital_boards)
        form_layout.addRow("Number of Digital Boards:", boards_spin)

        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

        self._boards_spin = boards_spin

    def get_num_digital_boards(self) -> int:
        return self._boards_spin.value()


class ExportDialog(QDialog):
    """Dialog for exporting tournament data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Data")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        format_label = QLabel("Export format:")
        layout.addWidget(format_label)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["CSV", "JSON"])
        layout.addWidget(self._format_combo)

        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("Select file path...")
        self._file_edit.setReadOnly(True)
        layout.addWidget(self._file_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        layout.addWidget(browse_btn)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        export_btn = QPushButton("Export")
        export_btn.setDefault(True)
        export_btn.clicked.connect(self.accept)
        button_layout.addWidget(export_btn)

        layout.addLayout(button_layout)

    def _browse_file(self):
        format_ext = "csv" if self._format_combo.currentText() == "CSV" else "json"
        filter_str = f"{format_ext.upper()} Files (*.{format_ext})"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save File", f"tournament_export.{format_ext}", filter_str
        )
        if file_path:
            self._file_edit.setText(file_path)

    def get_format(self) -> str:
        return self._format_combo.currentText()

    def get_file_path(self) -> str:
        return self._file_edit.text()
