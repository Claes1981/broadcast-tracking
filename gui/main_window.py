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
    QFileDialog,
    QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from config import (
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    LEFT_PANEL_WIDTH,
    RIGHT_PANEL_WIDTH,
)
from database import (
    get_pairing_by_id,
    open_tournament,
    get_tournament,
)
from logic import remove_pairing, edit_pairing
from gui.styles import (
    BUTTON_PRIMARY_STYLE,
    BUTTON_SECONDARY_STYLE,
    create_card_style_from_data,
    create_status_text_from_data,
)
from gui.dialogs import (
    NewTournamentDialog,
    FetchPairingsDialog,
    SettingsDialog,
    ExportDialog,
    ManualRoundDialog,
    EditPairingDialog,
)
from utils.export import export_to_csv, export_to_json
from gui.presenters import (
    ScraperPresenter,
    ManualEntryPresenter,
    RoundViewPresenter,
    AllocationPresenter,
)
from gui.presenters.round_view_presenter import PairingCardData


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
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

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
        splitter.setSizes([LEFT_PANEL_WIDTH, RIGHT_PANEL_WIDTH])

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
        """Load round labels into the combo box."""
        self._round_combo.clear()
        for label in self._round_view_presenter.get_round_labels():
            self._round_combo.addItem(label)

    def _load_participants(self):
        """Load participant rows into the table."""
        self._players_table.setRowCount(0)
        rows = self._round_view_presenter.get_participant_rows()

        for i, row in enumerate(rows):
            self._players_table.insertRow(i)
            self._players_table.setItem(i, 0, QTableWidgetItem(str(row.rank)))
            self._players_table.setItem(i, 1, QTableWidgetItem(row.name))
            self._players_table.setItem(i, 2, QTableWidgetItem(str(row.digital_count)))

    def _on_round_changed(self, round_str: str):
        """Handle round selection change."""
        if not round_str or not self.session:
            return

        round_obj = self._round_view_presenter.get_round_by_label(round_str)
        if round_obj is None:
            return
        self.current_round = round_obj
        self._load_pairings(round_obj)

    def _load_pairings(self, round_obj):
        """Load pairing cards for the selected round."""
        self._pairings_layout.addWidget(QWidget())
        while self._pairings_layout.count() > 1:
            item = self._pairings_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        cards = self._round_view_presenter.get_pairing_cards(round_obj)
        for card_data in cards:
            card = self._create_pairing_card(card_data)
            self._pairings_layout.addWidget(card)

    def _create_pairing_card(self, card_data: PairingCardData) -> QWidget:
        """Create a pairing card widget from presenter data."""
        card = QWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)

        self._add_pairing_title(layout, card_data)
        self._add_pairing_status(layout, card_data)
        self._add_pairing_stats(layout, card_data)
        self._add_pairing_controls(layout, card_data)

        card.setStyleSheet(create_card_style_from_data(card_data))

        return card

    def _add_pairing_title(self, layout: QVBoxLayout, data: PairingCardData):
        """Add participant names to pairing card."""
        title = QLabel(f"{data.p1_name} vs {data.p2_name}")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

    def _add_pairing_status(self, layout: QVBoxLayout, data: PairingCardData):
        """Add assignment status to pairing card."""
        status_text = create_status_text_from_data(data)
        status = QLabel(status_text)
        status.setStyleSheet("font-size: 12px;")
        layout.addWidget(status)

    def _add_pairing_stats(self, layout: QVBoxLayout, data: PairingCardData):
        """Add digital round statistics to pairing card."""
        combined = QLabel(
            f"Combined digital rounds: {data.p1_count} + {data.p2_count} = {data.combined_count}"
        )
        combined.setStyleSheet("font-size: 11px; color: #718096;")
        layout.addWidget(combined)

    def _add_pairing_controls(self, layout: QVBoxLayout, data: PairingCardData):
        """Add control buttons to pairing card."""
        button_layout = QHBoxLayout()
        pairing_id = data.pairing.id

        if data.digital_label:
            remove_assignment_btn = QPushButton("Remove Assignment")
            remove_assignment_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
            remove_assignment_btn.clicked.connect(
                lambda checked, pid=pairing_id: self._remove_assignment(pid)
            )
            button_layout.addWidget(remove_assignment_btn)
        else:
            assign_btn = QPushButton("Assign")
            assign_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
            assign_btn.clicked.connect(
                lambda checked, pid=pairing_id: self._manual_assign(pid)
            )
            button_layout.addWidget(assign_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        edit_btn.clicked.connect(
            lambda checked, pid=pairing_id: self._edit_pairing(pid)
        )
        button_layout.addWidget(edit_btn)

        remove_pairing_btn = QPushButton("Remove Pairing")
        remove_pairing_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        remove_pairing_btn.clicked.connect(
            lambda checked, pid=pairing_id: self._remove_pairing(pid)
        )
        button_layout.addWidget(remove_pairing_btn)

        toggle_btn = self._create_toggle_button(data.is_excluded, pairing_id)
        button_layout.addWidget(toggle_btn)

        layout.addLayout(button_layout)

    def _create_toggle_button(self, is_excluded: bool, pairing_id: int) -> QPushButton:
        """Create exclude/include toggle button."""
        text = "Include" if is_excluded else "Exclude"

        toggle_btn = QPushButton(text)
        toggle_btn.setStyleSheet(BUTTON_SECONDARY_STYLE)
        toggle_btn.clicked.connect(
            lambda checked, pid=pairing_id: self._toggle_exclude(pid)
        )
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
        self._allocation_presenter.num_digital_boards = num_boards
        self._allocation_presenter.allocate_round(self.current_round.id, self)

    def _clear_assignments(self):
        if not self.current_round:
            QMessageBox.warning(self, "Warning", "Please select a round first")
            return

        self._allocation_presenter.clear_round(self.current_round.id, self)

    def _manual_assign(self, pairing_id: int):
        self._allocation_presenter.manual_assign(pairing_id, self)

    def _remove_assignment(self, pairing_id: int):
        self._allocation_presenter.remove_assignment(pairing_id, self)

    def _edit_pairing(self, pairing_id: int):
        pairing = get_pairing_by_id(self.session, pairing_id)
        if not pairing:
            return

        dialog = EditPairingDialog(
            self,
            pairing.participant1.name,
            pairing.participant2.name,
        )

        if not dialog.exec():
            return

        try:
            new_p1, new_p2 = dialog.get_data()
            edit_pairing(self.session, pairing_id, new_p1, new_p2)
            self._refresh_current_view()
            QMessageBox.information(self, "Success", "Pairing updated")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to edit pairing: {e}")

    def _remove_pairing(self, pairing_id: int):
        reply = QMessageBox.question(
            self,
            "Confirm",
            "Remove this pairing?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                remove_pairing(self.session, pairing_id)
                self._refresh_current_view()
                QMessageBox.information(self, "Success", "Pairing removed")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove pairing: {e}")

    def _toggle_exclude(self, pairing_id: int):
        self._allocation_presenter.toggle_exclude(pairing_id, self)

    def _previous_round(self):
        idx = self._round_combo.currentIndex() - 1
        if idx >= 0:
            self._round_combo.setCurrentIndex(idx)

    def _next_round(self):
        idx = self._round_combo.currentIndex() + 1
        if idx < self._round_combo.count():
            self._round_combo.setCurrentIndex(idx)

    @property
    def _scraper_presenter(self) -> ScraperPresenter:
        """Lazily create scraper presenter."""
        if not hasattr(self, "_scraper_presenter_instance"):
            self._scraper_presenter_instance = ScraperPresenter(
                self.session, self.tournament_id, self._on_rounds_fetched
            )
        return self._scraper_presenter_instance

    @_scraper_presenter.setter
    def _scraper_presenter(self, value: ScraperPresenter):
        self._scraper_presenter_instance = value

    @property
    def _manual_entry_presenter(self) -> ManualEntryPresenter:
        """Lazily create manual entry presenter."""
        if not hasattr(self, "_manual_entry_presenter_instance"):
            self._manual_entry_presenter_instance = ManualEntryPresenter(
                self.session, self.tournament_id, self._on_round_added
            )
        return self._manual_entry_presenter_instance

    @_manual_entry_presenter.setter
    def _manual_entry_presenter(self, value: ManualEntryPresenter):
        self._manual_entry_presenter_instance = value

    @property
    def _round_view_presenter(self) -> RoundViewPresenter:
        """Lazily create round view presenter."""
        if not hasattr(self, "_round_view_presenter_instance"):
            self._round_view_presenter_instance = RoundViewPresenter(
                self.session, self.tournament_id
            )
        return self._round_view_presenter_instance

    @_round_view_presenter.setter
    def _round_view_presenter(self, value: RoundViewPresenter):
        self._round_view_presenter_instance = value

    @property
    def _allocation_presenter(self) -> AllocationPresenter:
        """Lazily create allocation presenter."""
        if not hasattr(self, "_allocation_presenter_instance"):
            self._allocation_presenter_instance = AllocationPresenter(
                self.session,
                self.tournament_id,
                self.num_digital_boards,
                self._on_allocated,
                self._on_cleared,
                self._refresh_current_view,
            )
        return self._allocation_presenter_instance

    @_allocation_presenter.setter
    def _allocation_presenter(self, value: AllocationPresenter):
        self._allocation_presenter_instance = value

    def _on_allocated(self, count: int) -> None:
        """Callback when boards are allocated."""
        self._refresh_current_view()

    def _on_cleared(self, count: int) -> None:
        """Callback when assignments are cleared."""
        self._refresh_current_view()

    def _on_rounds_fetched(self, count: int) -> None:
        """Callback when scraper imports rounds."""
        self._load_rounds()
        self._load_participants()
        self._select_last_round()
        QMessageBox.information(self, "Success", f"Fetched {count} round(s)")

    def _on_round_added(self, round_num: int, pairing_count: int) -> None:
        """Callback when manual round is added."""
        self._load_rounds()
        self._load_participants()
        self._select_last_round()
        QMessageBox.information(
            self, "Success", f"Added Round {round_num} with {pairing_count} pairing(s)"
        )

    def _select_last_round(self):
        """Select the last round in the combo box."""
        if self._round_combo.count() > 0:
            self._round_combo.setCurrentIndex(self._round_combo.count() - 1)

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
        if not self.session:
            QMessageBox.warning(self, "No tournament", "Please create or open a tournament first.")
            return

        tournament = get_tournament(self.session, self.tournament_id)
        existing_url = tournament.source_url or ""

        dialog = FetchPairingsDialog(self, existing_url)
        if dialog.exec():
            url = dialog.get_url()
            if url:
                self._do_fetch_pairings(url)

    def _do_fetch_pairings(self, url: str):
        try:
            result = self._scraper_presenter.fetch_and_import(url)
            if result == -1:
                QMessageBox.warning(
                    self, "Warning", "No rounds found at the specified URL"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch pairings: {e}")

    def _show_settings(self):
        dialog = SettingsDialog(self, self._boards_spin.value())
        if dialog.exec():
            self._boards_spin.setValue(dialog.get_num_digital_boards())
            self.num_digital_boards = dialog.get_num_digital_boards()

    def _manual_add_round(self):
        if not self.session:
            QMessageBox.warning(self, "Error", "Please open a tournament first")
            return

        next_round_num = self._manual_entry_presenter.get_next_round_number()
        participant_names = self._manual_entry_presenter.get_participant_names()
        dialog = ManualRoundDialog(self, next_round_num, participant_names)

        if not dialog.exec():
            return

        try:
            round_num, pairings_dict = dialog.get_data()
            self._manual_entry_presenter.import_manual_round(round_num, pairings_dict)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add round: {e}")

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
