"""
GUI Tests for Broadcast Board Tracker

Tests for the PyQt6 GUI components including:
- Main window functionality
- Dialog interactions
- Manual data entry workflows
- Error handling in GUI
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Need to check if we can import PyQt6
try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QSignalBlocker

    HAS_QT = True
except ImportError:
    HAS_QT = False


# Skip all tests if PyQt6 is not available
pytestmark = pytest.mark.skipif(not HAS_QT, reason="PyQt6 not available")


from gui.dialogs import (
    NewTournamentDialog,
    FetchPairingsDialog,
    SettingsDialog,
    ExportDialog,
)


# ============================================================================
# GUI TESTS - Dialogs
# ============================================================================


@pytest.fixture
def qt_app():
    """Create a QApplication for testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


class TestNewTournamentDialog:
    """Tests for the new tournament dialog."""

    def test_dialog_initialization(self, qt_app):
        """Test dialog creates without errors."""
        dialog = NewTournamentDialog()

        assert dialog.windowTitle() == "New Tournament"
        assert dialog.minimumWidth() == 400

    def test_dialog_with_data(self, qt_app):
        """Test dialog with pre-filled data."""
        dialog = NewTournamentDialog()

        # Access private attributes to set test data
        dialog._name_edit.setText("Test Tournament")
        dialog._url_edit.setText("https://example.com")
        dialog._type_combo.setCurrentText("team")

        name, url, ttype = dialog.get_data()

        assert name == "Test Tournament"
        assert url == "https://example.com"
        assert ttype == "team"

    def test_dialog_empty_data(self, qt_app):
        """Test dialog with empty data."""
        dialog = NewTournamentDialog()

        name, url, ttype = dialog.get_data()

        assert name == ""
        assert url == ""
        assert ttype == "individual"  # Default


class TestFetchPairingsDialog:
    """Tests for the fetch pairings dialog."""

    def test_dialog_initialization(self, qt_app):
        """Test dialog creates without errors."""
        dialog = FetchPairingsDialog()

        assert dialog.windowTitle() == "Fetch Pairings"

    def test_dialog_with_existing_url(self, qt_app):
        """Test dialog with existing URL."""
        existing_url = "https://member.schack.se/test?id=123"
        dialog = FetchPairingsDialog(existing_url=existing_url)

        assert dialog.get_url() == existing_url

    def test_set_available_rounds(self, qt_app):
        """Test setting available rounds."""
        dialog = FetchPairingsDialog()

        dialog.set_available_rounds([1, 2, 3, 4, 5])

        assert dialog._rounds_list == [1, 2, 3, 4, 5]

    def test_set_empty_rounds(self, qt_app):
        """Test setting empty rounds list."""
        dialog = FetchPairingsDialog()

        dialog.set_available_rounds([])

        assert dialog._rounds_list == []


class TestSettingsDialog:
    """Tests for the settings dialog."""

    def test_dialog_initialization(self, qt_app):
        """Test dialog creates without errors."""
        dialog = SettingsDialog()

        assert dialog.windowTitle() == "Settings"

    def test_dialog_with_custom_boards(self, qt_app):
        """Test dialog with custom number of boards."""
        dialog = SettingsDialog(num_digital_boards=8)

        assert dialog.get_num_digital_boards() == 8

    def test_boards_range(self, qt_app):
        """Test that board count is within valid range."""
        dialog = SettingsDialog()

        # Access private attribute
        assert dialog._boards_spin.minimum() == 1
        assert dialog._boards_spin.maximum() == 100


class TestExportDialog:
    """Tests for the export dialog."""

    def test_dialog_initialization(self, qt_app):
        """Test dialog creates without errors."""
        dialog = ExportDialog()

        assert dialog.windowTitle() == "Export Data"

    def test_get_format(self, qt_app):
        """Test getting export format."""
        dialog = ExportDialog()

        # Default should be CSV
        assert dialog.get_format() == "CSV"

        # Change to JSON
        dialog._format_combo.setCurrentText("JSON")
        assert dialog.get_format() == "JSON"

    def test_get_file_path(self, qt_app):
        """Test getting file path."""
        dialog = ExportDialog()

        # Initially empty
        assert dialog.get_file_path() == ""

        # Set a path
        dialog._file_edit.setText("/tmp/test.csv")
        assert dialog.get_file_path() == "/tmp/test.csv"


# ============================================================================
# MANUAL DATA ENTRY WORKFLOW TESTS
# ============================================================================


class TestManualDataEntryWorkflow:
    """Tests for complete manual data entry workflow."""

    @patch("gui.main_window.QMessageBox")
    @patch("gui.main_window.NewTournamentDialog")
    def test_create_tournament_manually(self, mock_dialog, mock_messagebox, qt_app):
        """Test creating a tournament through GUI."""
        from gui.main_window import MainWindow

        # Mock dialog
        mock_instance = Mock()
        mock_instance.exec.return_value = True
        mock_instance.get_data.return_value = ("Manual Tournament", "", "individual")
        mock_dialog.return_value = mock_instance

        # Create window
        window = MainWindow()

        # Trigger new tournament
        window._new_tournament()

        # Verify dialog was called
        mock_dialog.assert_called_once()

    @patch("gui.main_window.QMessageBox")
    def test_manual_pairing_entry_workflow(self, mock_messagebox, qt_app):
        """Test complete manual pairing entry workflow."""
        from database import create_tournament, get_session
        from logic.tournament import import_rounds_from_data
        from logic.pairing import RoundData, PairingData
        import tempfile
        import os

        # Create tournament
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock database path
            from database import init_db

            original_get_path = init_db.get_database_path

            def mock_get_path(name):
                return os.path.join(temp_dir, "test.sqlite")

            init_db.get_database_path = mock_get_path

            try:
                db_path, tournament_id = create_tournament("Manual Entry Test")
                session = get_session(db_path)

                # Manually enter pairings for round 1
                round_data = RoundData(
                    round_number=1,
                    pairings=[
                        PairingData("Team A", "Team B", board_number=1),
                        PairingData("Team C", "Team D", board_number=2),
                        PairingData("Team E", "Team F", board_number=3),
                    ],
                )

                import_rounds_from_data(session, tournament_id, [round_data], "team")

                # Verify data was entered
                from database.queries import get_all_rounds, get_round_pairings

                rounds = get_all_rounds(session, tournament_id)
                assert len(rounds) == 1

                pairings = get_round_pairings(session, rounds[0].id)
                assert len(pairings) == 3

                session.close()
            finally:
                init_db.get_database_path = original_get_path


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestGuiErrorHandling:
    """Tests for error handling in GUI."""

    @patch("gui.main_window.QMessageBox")
    def test_load_nonexistent_tournament(self, mock_messagebox, qt_app):
        """Test loading a tournament that doesn't exist."""
        from gui.main_window import MainWindow

        window = MainWindow()

        # Try to load non-existent database
        window.load_tournament("/nonexistent/path.sqlite")

        # Should show error message
        mock_messagebox.critical.assert_called_once()

    @patch("gui.main_window.QMessageBox")
    def test_allocate_without_round(self, mock_messagebox, qt_app):
        """Test allocating boards without selecting a round."""
        from gui.main_window import MainWindow

        window = MainWindow()

        # Try to allocate without round
        window._allocate_digital_boards()

        # Should show warning
        mock_messagebox.warning.assert_called_once()

    @patch("gui.main_window.QMessageBox")
    def test_clear_without_round(self, mock_messagebox, qt_app):
        """Test clearing assignments without selecting a round."""
        from gui.main_window import MainWindow

        window = MainWindow()

        # Try to clear without round
        window._clear_assignments()

        # Should show warning
        mock_messagebox.warning.assert_called_once()


# ============================================================================
# OFFLINE MODE GUI TESTS
# ============================================================================


class TestOfflineModeGui:
    """Tests for offline mode in GUI."""

    @patch("gui.main_window.QMessageBox")
    @patch("gui.main_window.SchackSeScraper")
    def test_fetch_with_network_error(self, mock_scraper, mock_messagebox, qt_app):
        """Test fetching pairings when network is down."""
        from gui.main_window import MainWindow
        from database import create_tournament, get_session

        # Create a tournament first
        import tempfile
        import os
        from database import init_db

        with tempfile.TemporaryDirectory() as temp_dir:
            original_get_path = init_db.get_database_path

            def mock_get_path(name):
                return os.path.join(temp_dir, "test.sqlite")

            init_db.get_database_path = mock_get_path

            try:
                db_path, tournament_id = create_tournament("Offline Test")

                window = MainWindow()
                window.db_path = db_path
                window.tournament_id = tournament_id
                window.session = get_session(db_path)

                # Mock scraper to raise network error
                mock_scraper_instance = Mock()
                mock_scraper_instance.fetch_all_rounds.side_effect = Exception(
                    "Network error"
                )
                mock_scraper.return_value = mock_scraper_instance

                # Try to fetch
                window._do_fetch_pairings("https://member.schack.se/test")

                # Should show error
                mock_messagebox.critical.assert_called_once()

                window.session.close()
            finally:
                init_db.get_database_path = original_get_path

    @patch("gui.main_window.QMessageBox")
    def test_manual_entry_as_fallback(self, mock_messagebox, qt_app):
        """Test that manual entry works as fallback when scraper fails."""
        from database import create_tournament, get_session
        from logic.tournament import import_rounds_from_data
        from logic.pairing import RoundData, PairingData
        import tempfile
        import os
        from database import init_db

        with tempfile.TemporaryDirectory() as temp_dir:
            original_get_path = init_db.get_database_path

            def mock_get_path(name):
                return os.path.join(temp_dir, "test.sqlite")

            init_db.get_database_path = mock_get_path

            try:
                # Create tournament without URL
                db_path, tournament_id = create_tournament(
                    "Manual Fallback", source_url=None
                )
                session = get_session(db_path)

                # Manually enter data as fallback
                rounds_data = [
                    RoundData(
                        round_number=1,
                        pairings=[
                            PairingData("A", "B"),
                            PairingData("C", "D"),
                        ],
                    ),
                    RoundData(
                        round_number=2,
                        pairings=[
                            PairingData("A", "C"),
                            PairingData("B", "D"),
                        ],
                    ),
                ]

                import_rounds_from_data(session, tournament_id, rounds_data, "team")

                # Verify data
                from database.queries import get_all_rounds

                rounds = get_all_rounds(session, tournament_id)
                assert len(rounds) == 2

                session.close()
            finally:
                init_db.get_database_path = original_get_path


# ============================================================================
# GUI STATE MANAGEMENT TESTS
# ============================================================================


class TestGuiStateManagement:
    """Tests for GUI state management."""

    def test_round_navigation(self, qt_app):
        """Test navigating between rounds."""
        from gui.main_window import MainWindow

        window = MainWindow()

        # Add some mock rounds
        window._round_combo.addItem("Round 1")
        window._round_combo.addItem("Round 2")
        window._round_combo.addItem("Round 3")

        # Start at round 1
        window._round_combo.setCurrentIndex(0)

        # Go to next
        window._next_round()
        assert window._round_combo.currentIndex() == 1

        # Go to next again
        window._next_round()
        assert window._round_combo.currentIndex() == 2

        # Can't go further
        window._next_round()
        assert window._round_combo.currentIndex() == 2

        # Go to previous
        window._previous_round()
        assert window._round_combo.currentIndex() == 1

    def test_digital_boards_spinbox(self, qt_app):
        """Test digital boards spinbox."""
        from gui.main_window import MainWindow

        window = MainWindow()

        # Default value
        assert window._boards_spin.value() == 5

        # Change value
        window._boards_spin.setValue(8)
        assert window._boards_spin.value() == 8

        # Min/max
        window._boards_spin.setMinimum(1)
        window._boards_spin.setMaximum(100)
        assert window._boards_spin.minimum() == 1
        assert window._boards_spin.maximum() == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
