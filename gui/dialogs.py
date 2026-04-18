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
    QListWidget,
    QListWidgetItem,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
)
from PyQt6.QtCore import Qt
from typing import Optional

from logic.pairing import PairingData


def _create_button_layout(
    cancel_text: str = "Cancel", ok_text: str = "OK"
) -> QHBoxLayout:
    """Create a standard button layout with Cancel and OK buttons."""
    layout = QHBoxLayout()
    layout.addStretch()

    cancel_btn = QPushButton(cancel_text)
    layout.addWidget(cancel_btn)

    ok_btn = QPushButton(ok_text)
    ok_btn.setDefault(True)
    layout.addWidget(ok_btn)

    return layout, cancel_btn, ok_btn


def _validate_non_empty(text: str, field_name: str) -> bool:
    """Validate that a text field is not empty."""
    return len(text.strip()) > 0


class NewTournamentDialog(QDialog):
    """Dialog for creating a new tournament."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Tournament")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form_layout = self._create_form_layout()
        layout.addLayout(form_layout)

        button_layout, cancel_btn, create_btn = _create_button_layout(
            "Cancel", "Create"
        )
        cancel_btn.clicked.connect(self.reject)
        create_btn.clicked.connect(self._on_create)
        layout.addLayout(button_layout)

    def _create_form_layout(self) -> QFormLayout:
        """Create and populate the form layout."""
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

        self._name_edit = name_edit
        self._url_edit = url_edit
        self._type_combo = type_combo

        return form_layout

    def _on_create(self):
        """Handle create button click with validation."""
        if not _validate_non_empty(self._name_edit.text(), "Tournament Name"):
            QMessageBox.warning(self, "Error", "Please enter a tournament name")
            return
        self.accept()

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
        self._rounds_list: list[int] = []
        self._setup_ui(existing_url)

    def _setup_ui(self, existing_url: str):
        layout = QVBoxLayout(self)

        self._add_info_section(layout)
        self._add_url_input(layout, existing_url)
        self._add_rounds_display(layout)
        self._add_buttons(layout)

    def _add_info_section(self, layout: QVBoxLayout):
        """Add information label section."""
        info_label = QLabel(
            "Enter the tournament URL to fetch available rounds.\n"
            "Example: https://member.schack.se/ShowTournamentServlet?id=16441"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

    def _add_url_input(self, layout: QVBoxLayout, existing_url: str):
        """Add URL input field."""
        url_edit = QLineEdit(existing_url)
        url_edit.setPlaceholderText(
            "https://member.schack.se/ShowTournamentServlet?id=XXXXX"
        )
        layout.addWidget(url_edit)
        self._url_edit = url_edit

    def _add_rounds_display(self, layout: QVBoxLayout):
        """Add rounds display label."""
        self._rounds_label = QLabel("Available rounds will appear here...")
        layout.addWidget(self._rounds_label)

    def _add_buttons(self, layout: QVBoxLayout):
        """Add action buttons."""
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        fetch_btn = QPushButton("Fetch Rounds")
        fetch_btn.clicked.connect(self._on_fetch)
        button_layout.addWidget(fetch_btn)

        layout.addLayout(button_layout)

    def _on_fetch(self):
        """Handle fetch button click with validation."""
        url = self._url_edit.text().strip()
        if not _validate_non_empty(url, "URL"):
            QMessageBox.warning(self, "Error", "Please enter a URL")
            return

        self._rounds_label.setText("Fetching...")
        self._rounds_list = []
        self.accept()

    def get_url(self) -> str:
        return self._url_edit.text().strip()

    def set_available_rounds(self, rounds: list[int]):
        self._rounds_list = rounds
        self._update_rounds_display(rounds)

    def _update_rounds_display(self, rounds: list[int]):
        """Update the rounds display label."""
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

        form_layout = self._create_form_layout(num_digital_boards)
        layout.addLayout(form_layout)

        button_layout, cancel_btn, ok_btn = _create_button_layout()
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self.accept)
        layout.addLayout(button_layout)

    def _create_form_layout(self, num_digital_boards: int) -> QFormLayout:
        """Create and populate the form layout."""
        form_layout = QFormLayout()

        boards_spin = QSpinBox()
        boards_spin.setRange(1, 100)
        boards_spin.setValue(num_digital_boards)
        form_layout.addRow("Number of Digital Boards:", boards_spin)

        self._boards_spin = boards_spin

        return form_layout

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

        self._add_format_selection(layout)
        self._add_file_selection(layout)
        self._add_buttons(layout)

    def _add_format_selection(self, layout: QVBoxLayout):
        """Add export format selection."""
        format_label = QLabel("Export format:")
        layout.addWidget(format_label)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["CSV", "JSON"])
        layout.addWidget(self._format_combo)

    def _add_file_selection(self, layout: QVBoxLayout):
        """Add file path selection."""
        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("Select file path...")
        self._file_edit.setReadOnly(True)
        layout.addWidget(self._file_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        layout.addWidget(browse_btn)

    def _add_buttons(self, layout: QVBoxLayout):
        """Add action buttons."""
        button_layout, cancel_btn, export_btn = _create_button_layout(
            "Cancel", "Export"
        )
        cancel_btn.clicked.connect(self.reject)
        export_btn.clicked.connect(self._on_export)
        layout.addLayout(button_layout)

    def _on_export(self):
        """Handle export button click with validation."""
        file_path = self._file_edit.text()
        if not _validate_non_empty(file_path, "File path"):
            QMessageBox.warning(self, "Error", "Please select a file path")
            return
        self.accept()

    def _browse_file(self):
        """Open file browser dialog."""
        format_ext = self._get_file_extension()
        filter_str = f"{format_ext.upper()} Files (*.{format_ext})"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save File", f"tournament_export.{format_ext}", filter_str
        )
        if file_path:
            self._file_edit.setText(file_path)

    def _get_file_extension(self) -> str:
        """Get file extension based on selected format."""
        return "csv" if self._format_combo.currentText() == "CSV" else "json"

    def get_format(self) -> str:
        return self._format_combo.currentText()

    def get_file_path(self) -> str:
        return self._file_edit.text()


class ManualPairingDialog(QDialog):
    """Dialog for entering a single pairing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Pairing")
        self.setMinimumWidth(350)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form_layout = self._create_form_layout()
        layout.addLayout(form_layout)

        button_layout, cancel_btn, ok_btn = _create_button_layout()
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self._on_ok)
        layout.addLayout(button_layout)

    def _create_form_layout(self) -> QFormLayout:
        """Create and populate the form layout."""
        form_layout = QFormLayout()

        p1_edit = QLineEdit()
        p1_edit.setPlaceholderText("First participant name")
        form_layout.addRow("Participant 1:", p1_edit)

        p2_edit = QLineEdit()
        p2_edit.setPlaceholderText("Second participant name")
        form_layout.addRow("Participant 2:", p2_edit)

        board_spin = QSpinBox()
        board_spin.setRange(1, 999)
        board_spin.setValue(1)
        form_layout.addRow("Board Number:", board_spin)

        self._p1_edit = p1_edit
        self._p2_edit = p2_edit
        self._board_spin = board_spin

        return form_layout

    def _on_ok(self):
        """Handle OK button click with validation."""
        p1 = self._p1_edit.text().strip()
        p2 = self._p2_edit.text().strip()

        if not _validate_non_empty(p1, "Participant 1"):
            QMessageBox.warning(self, "Error", "Please enter first participant name")
            return
        if not _validate_non_empty(p2, "Participant 2"):
            QMessageBox.warning(self, "Error", "Please enter second participant name")
            return

        self.accept()

    def get_data(self) -> tuple[str, str, int]:
        return (
            self._p1_edit.text().strip(),
            self._p2_edit.text().strip(),
            self._board_spin.value(),
        )


class ManualRoundDialog(QDialog):
    """Dialog for manually entering a round with pairings."""

    def __init__(self, parent=None, round_number: int = 1):
        super().__init__(parent)
        self.setWindowTitle("Add Round Manually")
        self.setMinimumWidth(500)
        self._setup_ui(round_number)

    def _setup_ui(self, round_number: int):
        layout = QVBoxLayout(self)

        self._add_round_number_input(layout, round_number)
        self._add_pairings_table(layout)
        self._add_pairing_controls(layout)
        self._add_buttons(layout)

    def _add_round_number_input(self, layout: QVBoxLayout, round_number: int):
        """Add round number input field."""
        form_layout = QFormLayout()

        round_spin = QSpinBox()
        round_spin.setRange(1, 100)
        round_spin.setValue(round_number)
        form_layout.addRow("Round Number:", round_spin)

        layout.addLayout(form_layout)
        self._round_spin = round_spin

    def _add_pairings_table(self, layout: QVBoxLayout):
        """Add pairings table widget."""
        pairings_label = QLabel("Pairings:")
        layout.addWidget(pairings_label)

        self._pairings_table = QTableWidget()
        self._pairings_table.setColumnCount(3)
        self._pairings_table.setHorizontalHeaderLabels(
            ["Participant 1", "Participant 2", "Board"]
        )
        self._pairings_table.setMinimumHeight(200)
        layout.addWidget(self._pairings_table)

    def _add_pairing_controls(self, layout: QVBoxLayout):
        """Add pairing control buttons."""
        buttons_layout = QHBoxLayout()

        add_btn = QPushButton("Add Pairing")
        add_btn.clicked.connect(self._add_pairing)
        buttons_layout.addWidget(add_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_pairing)
        buttons_layout.addWidget(remove_btn)

        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

    def _add_buttons(self, layout: QVBoxLayout):
        """Add dialog action buttons."""
        button_layout, cancel_btn, add_btn = _create_button_layout(
            "Cancel", "Add Round"
        )
        cancel_btn.clicked.connect(self.reject)
        add_btn.clicked.connect(self._on_add_round)
        layout.addLayout(button_layout)

    def _add_pairing(self, p1: str = "", p2: str = "", board: int = 1):
        """Add a pairing to the table."""
        if not p1 or not p2:
            dialog = ManualPairingDialog(self)
            if not dialog.exec():
                return
            p1, p2, board = dialog.get_data()

        self._insert_pairing_row(p1, p2, board)

    def _insert_pairing_row(self, p1: str, p2: str, board: int):
        """Insert a pairing row into the table."""
        row = self._pairings_table.rowCount()
        self._pairings_table.insertRow(row)
        self._pairings_table.setItem(row, 0, QTableWidgetItem(p1))
        self._pairings_table.setItem(row, 1, QTableWidgetItem(p2))
        self._pairings_table.setItem(row, 2, QTableWidgetItem(str(board)))

    def _remove_pairing(self):
        """Remove selected pairing from table."""
        current_row = self._pairings_table.currentRow()
        if current_row >= 0:
            self._pairings_table.removeRow(current_row)

    def _on_add_round(self):
        """Handle add round button click with validation."""
        if not self._has_pairings():
            QMessageBox.warning(self, "Error", "Please add at least one pairing")
            return
        self.accept()

    def _has_pairings(self) -> bool:
        """Check if table has any pairings."""
        return self._pairings_table.rowCount() > 0

    def get_data(self) -> tuple[int, list[dict]]:
        """Get round number and pairings as list of dicts."""
        round_num = self._round_spin.value()
        pairings = self._extract_pairings_from_table()
        return round_num, pairings

    def _extract_pairings_from_table(self) -> list[dict]:
        """Extract pairings data from table."""
        pairings = []

        for row in range(self._pairings_table.rowCount()):
            pairing = self._get_pairing_from_row(row)
            pairings.append(pairing)

        return pairings

    def _get_pairing_from_row(self, row: int) -> dict:
        """Get pairing data from a specific row."""
        p1 = self._pairings_table.item(row, 0).text()
        p2 = self._pairings_table.item(row, 1).text()
        board = int(self._pairings_table.item(row, 2).text())

        return {
            "participant1": p1,
            "participant2": p2,
            "board_number": board,
        }
