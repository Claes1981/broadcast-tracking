from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QPushButton,
    QComboBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QAbstractItemView,
    QMessageBox,
    QMenu,
    QMenuBar,
    QFileDialog,
    QInputDialog,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from typing import Optional

from database import (
    get_all_participants,
    get_all_rounds,
    get_round,
    get_round_pairings,
    get_digital_assignment,
    count_digital_rounds_for_participant,
    get_max_round,
    open_tournament,
    get_tournament,
)
from logic import (
    allocate_digital_boards,
    clear_round_assignments,
    manually_assign_digital_board,
    exclude_from_digital,
    import_rounds_from_data,
    generate_digital_board_labels,
)
from scrapers import SchackSeScraper
from logic.pairing import RoundData, PairingData
from gui.styles import (
    DIGITAL_ASSIGNED,
    NOT_ASSIGNED,
    MANUALLY_EXCLUDED,
    MANUALLY_ASSIGNED,
    BUTTON_PRIMARY_STYLE,
    BUTTON_SECONDARY_STYLE,
    CARD_STYLE,
)
from gui.dialogs import (
    NewTournamentDialog,
    FetchPairingsDialog,
    SettingsDialog,
    ExportDialog,
    ManualRoundDialog,
)
from utils.export import export_to_csv, export_to_json


def _create_card_style(assignment) -> str:
    """Determine card style based on assignment status."""
    if not assignment:
        return CARD_STYLE + NOT_ASSIGNED

    if assignment.is_excluded:
        return CARD_STYLE + MANUALLY_EXCLUDED

    if assignment.digital_board_label:
        return CARD_STYLE + (
            MANUALLY_ASSIGNED if assignment.is_manual else DIGITAL_ASSIGNED
        )

    return CARD_STYLE + NOT_ASSIGNED


def _create_status_text(assignment) -> str:
    """Create status text based on assignment."""
    if not assignment:
        return "Not assigned"

    if assignment.is_excluded:
        return "EXCLUDED from digital boards"

    if assignment.digital_board_label:
        return f"Digital Board: {assignment.digital_board_label}"

    return "Not assigned"


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.db_path = None
        self.tournament_id = None
        self.session = None
        self.current_round = None
        self.num_digital_boards = 5

        self.setWindowTitle("Chess Tournament Digital Board Tracker")
        self.setMinimumSize(1200, 800)

        self._setup_menu()
        self._setup_ui()
        self._apply_styles()

    def _setup_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")

        new_action = QAction("New Tournament", self)
        new_action.triggered.connect(self._new_tournament)
        file_menu.addAction(new_action)

        open_action = QAction("Open Tournament", self)
        open_action.triggered.connect(self._open_tournament)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        export_csv_action = QAction("Export CSV...", self)
        export_csv_action.triggered.connect(lambda: self._export("CSV"))
        file_menu.addAction(export_csv_action)

        export_json_action = QAction("Export JSON...", self)
        export_json_action.triggered.connect(lambda: self._export("JSON"))
        file_menu.addAction(export_json_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        tournament_menu = menubar.addMenu("Tournament")

        fetch_action = QAction("Fetch Pairings...", self)
        fetch_action.triggered.connect(self._fetch_pairings)
        tournament_menu.addAction(fetch_action)

        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self._show_settings)
        tournament_menu.addAction(settings_action)

        round_menu = menubar.addMenu("Round")

        prev_action = QAction("Previous Round", self)
        prev_action.triggered.connect(self._previous_round)
        round_menu.addAction(prev_action)

        next_action = QAction("Next Round", self)
        next_action.triggered.connect(self._next_round)
        round_menu.addAction(next_action)

        round_menu.addSeparator()

        manual_round_action = QAction("Add Round Manually...", self)
        manual_round_action.triggered.connect(self._manual_add_round)
        round_menu.addAction(manual_round_action)

        allocate_action = QAction("Allocate Digital Boards", self)
        allocate_action.triggered.connect(self._allocate_digital_boards)
        round_menu.addAction(allocate_action)

        clear_action = QAction("Clear Current Round Assignments", self)
        clear_action.triggered.connect(self._clear_assignments)
        round_menu.addAction(clear_action)

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        top_bar = self._create_top_bar()
        main_layout.addWidget(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800])

        main_layout.addWidget(splitter)

        self._left_panel = left_panel
        self._right_panel = right_panel

    def _create_top_bar(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 5)

        self._tournament_label = QLabel("No tournament loaded")
        self._tournament_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self._tournament_label)

        layout.addWidget(QLabel("Round:"))

        self._round_combo = QComboBox()
        self._round_combo.setMinimumWidth(80)
        self._round_combo.currentTextChanged.connect(self._on_round_changed)
        layout.addWidget(self._round_combo)

        layout.addWidget(QLabel("Digital Boards:"))

        self._boards_spin = QSpinBox()
        self._boards_spin.setRange(1, 100)
        self._boards_spin.setValue(5)
        self._boards_spin.setMinimumWidth(60)
        layout.addWidget(self._boards_spin)

        layout.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        refresh_btn.clicked.connect(self._refresh_current_view)
        layout.addWidget(refresh_btn)

        allocate_btn = QPushButton("Allocate")
        allocate_btn.setStyleSheet(BUTTON_PRIMARY_STYLE)
        allocate_btn.clicked.connect(self._allocate_digital_boards)
        layout.addWidget(allocate_btn)

        return widget

    def _create_left_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 0, 5, 0)

        group = QGroupBox("Participants")
        group_layout = QVBoxLayout(group)

        self._players_table = QTableWidget()
        self._players_table.setColumnCount(3)
        self._players_table.setHorizontalHeaderLabels(
            ["Rank", "Name", "Digital Rounds"]
        )
        self._players_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._players_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._players_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        group_layout.addWidget(self._players_table)

        layout.addWidget(group)

        return widget

    def _create_right_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 0, 5, 0)

        group = QGroupBox("Current Round Pairings")
        group_layout = QVBoxLayout(group)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        self._pairings_widget = QWidget()
        self._pairings_layout = QVBoxLayout(self._pairings_widget)
        self._pairings_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area.setWidget(self._pairings_widget)
        group_layout.addWidget(scroll_area)

        layout.addWidget(group)

        return widget

    def _apply_styles(self):
        self._players_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e2e8f0;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """)

    def load_tournament(self, db_path: str):
        """Load a tournament from database."""
        try:
            self.session, self.tournament_id = open_tournament(db_path)
            self.db_path = db_path

            tournament = get_tournament(self.session, self.tournament_id)
            self._tournament_label.setText(f"Tournament: {tournament.name}")

            self._load_rounds()
            self._load_participants()

            if self._round_combo.count() > 0:
                self._round_combo.setCurrentIndex(0)

            QMessageBox.information(
                self, "Success", f"Loaded tournament: {tournament.name}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load tournament: {e}")
            if self.session:
                self.session.close()

    def _load_rounds(self):
        self._round_combo.clear()
        rounds = get_all_rounds(self.session, self.tournament_id)
        for round_obj in rounds:
            self._round_combo.addItem(f"Round {round_obj.round_number}")

    def _load_participants(self):
        self._players_table.setRowCount(0)

        participants = get_all_participants(self.session, self.tournament_id)
        participant_data = []

        for p in participants:
            digital_count = count_digital_rounds_for_participant(self.session, p.id)
            participant_data.append((p.id, p.name, digital_count))

        participant_data.sort(key=lambda x: (-x[2], x[1]))

        for i, (pid, name, digital_count) in enumerate(participant_data):
            self._players_table.insertRow(i)
            self._players_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self._players_table.setItem(i, 1, QTableWidgetItem(name))
            self._players_table.setItem(i, 2, QTableWidgetItem(str(digital_count)))

    def _on_round_changed(self, round_str: str):
        if not round_str or not self.session:
            return

        round_num = int(round_str.replace("Round ", ""))
        round_obj = get_round(self.session, self.tournament_id, round_num)
        self.current_round = round_obj

        self._load_pairings(round_obj)

    def _load_pairings(self, round_obj):
        self._pairings_layout.addWidget(QWidget())
        while self._pairings_layout.count() > 1:
            item = self._pairings_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        pairings = get_round_pairings(self.session, round_obj.id)

        for pairing in pairings:
            card = self._create_pairing_card(pairing)
            self._pairings_layout.addWidget(card)

    def _create_pairing_card(self, pairing) -> QWidget:
        card = QWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)

        self._add_pairing_title(layout, pairing)
        self._add_pairing_status(layout, pairing)
        self._add_pairing_stats(layout, pairing)
        self._add_pairing_controls(layout, pairing)

        assignment = get_digital_assignment(self.session, pairing.id)
        card.setStyleSheet(_create_card_style(assignment))

        return card

    def _add_pairing_title(self, layout: QVBoxLayout, pairing):
        """Add participant names to pairing card."""
        p1_name = pairing.participant1.name
        p2_name = pairing.participant2.name

        title = QLabel(f"{p1_name} vs {p2_name}")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

    def _add_pairing_status(self, layout: QVBoxLayout, pairing):
        """Add assignment status to pairing card."""
        assignment = get_digital_assignment(self.session, pairing.id)
        status_text = _create_status_text(assignment)

        status = QLabel(status_text)
        status.setStyleSheet("font-size: 12px;")
        layout.addWidget(status)

    def _add_pairing_stats(self, layout: QVBoxLayout, pairing):
        """Add digital round statistics to pairing card."""
        count1 = count_digital_rounds_for_participant(
            self.session, pairing.participant1_id
        )
        count2 = count_digital_rounds_for_participant(
            self.session, pairing.participant2_id
        )
        combined = QLabel(
            f"Combined digital rounds: {count1} + {count2} = {count1 + count2}"
        )
        combined.setStyleSheet("font-size: 11px; color: #718096;")
        layout.addWidget(combined)

    def _add_pairing_controls(self, layout: QVBoxLayout, pairing):
        """Add control buttons to pairing card."""
        button_layout = QHBoxLayout()
        assignment = get_digital_assignment(self.session, pairing.id)

        if assignment and assignment.digital_board_label:
            remove_btn = QPushButton("Remove")
            remove_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
            remove_btn.clicked.connect(lambda: self._remove_assignment(pairing.id))
            button_layout.addWidget(remove_btn)
        else:
            assign_btn = QPushButton("Assign")
            assign_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
            assign_btn.clicked.connect(lambda: self._manual_assign(pairing.id))
            button_layout.addWidget(assign_btn)

        toggle_btn = self._create_toggle_button(assignment)
        button_layout.addWidget(toggle_btn)

        layout.addLayout(button_layout)

    def _create_toggle_button(self, assignment) -> QPushButton:
        """Create exclude/include toggle button."""
        is_excluded = assignment and assignment.is_excluded
        text = "Include" if is_excluded else "Exclude"

        toggle_btn = QPushButton(text)
        toggle_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        return toggle_btn

    def _refresh_current_view(self):
        self._load_participants()
        if self.current_round:
            self._load_pairings(self.current_round)

    def _allocate_digital_boards(self):
        if not self.current_round:
            QMessageBox.warning(self, "Warning", "Please select a round first")
            return

        num_boards = self._boards_spin.value()
        self.num_digital_boards = num_boards

        try:
            allocate_digital_boards(self.session, self.current_round.id, num_boards)
            self._refresh_current_view()
            QMessageBox.information(
                self, "Success", f"Allocated {num_boards} digital boards"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to allocate: {e}")

    def _clear_assignments(self):
        if not self.current_round:
            QMessageBox.warning(self, "Warning", "Please select a round first")
            return

        reply = QMessageBox.question(
            self,
            "Confirm",
            "Clear all digital board assignments for this round?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                count = clear_round_assignments(self.session, self.current_round.id)
                self._refresh_current_view()
                QMessageBox.information(self, "Success", f"Cleared {count} assignments")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear: {e}")

    def _manual_assign(self, pairing_id: int):
        labels = generate_digital_board_labels(self.num_digital_boards)

        selected, ok = QInputDialog.getItem(
            self, "Assign Digital Board", "Choose a digital board:", labels, 0, False
        )

        if ok:
            try:
                manually_assign_digital_board(self.session, pairing_id, selected)
                self._refresh_current_view()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to assign: {e}")

    def _remove_assignment(self, pairing_id: int):
        try:
            manually_assign_digital_board(self.session, pairing_id, None)
            self._refresh_current_view()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to remove: {e}")

    def _toggle_exclude(self, pairing_id: int):
        assignment = get_digital_assignment(self.session, pairing_id)
        excluded = not (assignment and assignment.is_excluded)

        try:
            exclude_from_digital(self.session, pairing_id, excluded)
            self._refresh_current_view()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to toggle: {e}")

    def _previous_round(self):
        idx = self._round_combo.currentIndex() - 1
        if idx >= 0:
            self._round_combo.setCurrentIndex(idx)

    def _next_round(self):
        idx = self._round_combo.currentIndex() + 1
        if idx < self._round_combo.count():
            self._round_combo.setCurrentIndex(idx)

    def _new_tournament(self):
        dialog = NewTournamentDialog(self)
        if dialog.exec():
            name, url, ttype = dialog.get_data()
            try:
                from database import create_tournament

                db_path, tid = create_tournament(name, url, ttype)
                self.load_tournament(db_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create tournament: {e}")

    def _open_tournament(self):
        from config import DATA_DIR

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Tournament", DATA_DIR, "SQLite Files (*.sqlite)"
        )
        if file_path:
            self.load_tournament(file_path)

    def _fetch_pairings(self):
        tournament = get_tournament(self.session, self.tournament_id)
        existing_url = tournament.source_url or ""

        dialog = FetchPairingsDialog(self, existing_url)
        if dialog.exec():
            url = dialog.get_url()
            if url:
                self._do_fetch_pairings(url)

    def _do_fetch_pairings(self, url: str):
        scraper = SchackSeScraper()

        try:
            self._fetch_and_import_rounds(scraper, url)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch pairings: {e}")

    def _fetch_and_import_rounds(self, scraper: SchackSeScraper, url: str):
        """Fetch rounds from URL and import them."""
        name, rounds = scraper.fetch_all_rounds(url)

        if not rounds:
            QMessageBox.warning(self, "Warning", "No rounds found at the specified URL")
            return

        rounds_to_fetch = self._determine_rounds_to_fetch(rounds)
        tournament_type = get_tournament(
            self.session, self.tournament_id
        ).tournament_type

        for round_num in rounds_to_fetch:
            self._import_round_from_scraper(scraper, url, round_num, tournament_type)

        self._load_rounds()
        self._load_participants()
        self._select_last_round()

        QMessageBox.information(
            self, "Success", f"Fetched {len(rounds_to_fetch)} round(s)"
        )

    def _determine_rounds_to_fetch(self, rounds: list[int]) -> list[int]:
        """Determine which rounds need to be fetched."""
        rounds_to_fetch = []
        for r in rounds:
            if get_round(self.session, self.tournament_id, r) is None:
                rounds_to_fetch.append(r)

        if not rounds_to_fetch:
            if not self._confirm_overwrite():
                return []
            rounds_to_fetch = rounds

        return rounds_to_fetch

    def _confirm_overwrite(self) -> bool:
        """Ask user if they want to overwrite existing rounds."""
        reply = QMessageBox.question(
            self,
            "Confirm",
            f"All rounds already exist. Re-fetch and overwrite?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _import_round_from_scraper(
        self, scraper: SchackSeScraper, url: str, round_num: int, tournament_type: str
    ):
        """Import a single round from scraper."""
        pairings_data = scraper.fetch_round_pairings(url, round_num)
        pairings = self._create_pairing_data_from_scraper(pairings_data)
        round_data = RoundData(round_number=round_num, pairings=pairings)
        import_rounds_from_data(
            self.session, self.tournament_id, [round_data], tournament_type
        )

    def _create_pairing_data_from_scraper(
        self, pairings_data: list[dict]
    ) -> list[PairingData]:
        """Create PairingData objects from scraper data."""
        return [
            PairingData(
                participant1_name=p["participant1"],
                participant2_name=p["participant2"],
                board_number=p.get("board_number"),
                score1=p.get("score1"),
                score2=p.get("score2"),
            )
            for p in pairings_data
        ]

    def _select_last_round(self):
        """Select the last round in the combo box."""
        if self._round_combo.count() > 0:
            self._round_combo.setCurrentIndex(self._round_combo.count() - 1)

    def _show_settings(self):
        dialog = SettingsDialog(self, self._boards_spin.value())
        if dialog.exec():
            self._boards_spin.setValue(dialog.get_num_digital_boards())
            self.num_digital_boards = dialog.get_num_digital_boards()

    def _manual_add_round(self):
        if not self.session:
            QMessageBox.warning(self, "Error", "Please open a tournament first")
            return

        next_round_num = self._get_next_round_number()
        dialog = ManualRoundDialog(self, next_round_num)

        if not dialog.exec():
            return

        try:
            self._import_manual_round(dialog)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add round: {e}")

    def _get_next_round_number(self) -> int:
        """Calculate the next round number."""
        max_round = get_max_round(self.session, self.tournament_id)
        return max_round + 1 if max_round else 1

    def _import_manual_round(self, dialog: ManualRoundDialog):
        """Import a manually entered round."""
        round_num, pairings_dict = dialog.get_data()
        pairings = self._create_pairing_data_from_manual(pairings_dict)
        round_data = RoundData(round_number=round_num, pairings=pairings)
        tournament_type = get_tournament(
            self.session, self.tournament_id
        ).tournament_type

        import_rounds_from_data(
            self.session, self.tournament_id, [round_data], tournament_type
        )

        self._load_rounds()
        self._load_participants()
        self._select_last_round()

        QMessageBox.information(
            self,
            "Success",
            f"Added Round {round_num} with {len(pairings)} pairing(s)",
        )

    def _create_pairing_data_from_manual(
        self, pairings_dict: list[dict]
    ) -> list[PairingData]:
        """Create PairingData objects from manual entry."""
        return [
            PairingData(
                participant1_name=p["participant1"],
                participant2_name=p["participant2"],
                board_number=p.get("board_number"),
            )
            for p in pairings_dict
        ]

    def _export(self, format_type: str):
        dialog = ExportDialog(self)
        dialog._format_combo.setCurrentText(format_type)

        if dialog.exec():
            file_path = dialog.get_file_path()
            if not file_path:
                return

            try:
                if format_type == "CSV":
                    export_to_csv(self.session, self.tournament_id, file_path)
                else:
                    export_to_json(self.session, self.tournament_id, file_path)

                QMessageBox.information(self, "Success", f"Exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {e}")

    def closeEvent(self, event):
        if self.session:
            self.session.close()
        event.accept()
