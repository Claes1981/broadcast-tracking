"""Manual entry tests for Broadcast Board Tracker.

Offline manual data entry workflow without internet connection.
"""

import os
import pytest
from unittest.mock import Mock, patch


HAS_QT = True

from gui.dialogs import ManualRoundDialog, ManualPairingDialog
from database import create_tournament, get_session, get_all_rounds, get_round_pairings
from database.models import Round
from logic.tournament import create_round_from_data
from logic.pairing import RoundData, PairingData
from logic.allocator import allocate_digital_boards


# ============================================================================
# MANUAL ENTRY DIALOG TESTS
# ============================================================================


@pytest.fixture
def offline_tournament(qt_app, mock_database_path):
    """Create an offline tournament without URL."""
    with mock_database_path() as db_path:
        _, tournament_id = create_tournament(
            name="Offline Tournament",
            source_url=None,
            tournament_type="team",
        )
        session = get_session(db_path)
        yield {
            "db_path": db_path,
            "tournament_id": tournament_id,
            "session": session,
        }
        session.close()


class TestManualRoundDialog:
    """Tests for the manual round entry dialog."""

    def test_dialog_initialization(self, qt_app):
        """Test dialog creates without errors."""
        dialog = ManualRoundDialog()

        assert dialog.windowTitle() == "Add Round Manually"
        assert dialog.minimumWidth() >= 400

    def test_dialog_set_round_number(self, qt_app):
        """Test setting round number."""
        dialog = ManualRoundDialog()

        dialog._round_spin.setValue(3)
        assert dialog._round_spin.value() == 3

    def test_dialog_round_range(self, qt_app):
        """Test round number range."""
        dialog = ManualRoundDialog()

        assert dialog._round_spin.minimum() == 1
        assert dialog._round_spin.maximum() >= 100

    def test_dialog_add_pairing(self, qt_app):
        """Test adding pairings to the list."""
        dialog = ManualRoundDialog()

        # Add a pairing
        dialog._add_pairing("Team A", "Team B", 1)

        # Should have one row
        assert dialog._pairings_table.rowCount() == 1

    def test_dialog_get_data(self, qt_app):
        """Test getting round data from dialog."""
        dialog = ManualRoundDialog()

        dialog._round_spin.setValue(2)
        dialog._add_pairing("Player A", "Player B", 1)
        dialog._add_pairing("Player C", "Player D", 2)

        round_num, pairings = dialog.get_data()

        assert round_num == 2
        assert len(pairings) == 2
        assert pairings[0]["participant1"] == "Player A"
        assert pairings[0]["participant2"] == "Player B"
        assert pairings[0]["board_number"] == 1


class TestManualPairingDialog:
    """Tests for the manual pairing entry dialog."""

    def test_dialog_initialization(self, qt_app):
        """Test dialog creates without errors."""
        dialog = ManualPairingDialog()

        assert dialog.windowTitle() == "Add Pairing"

    def test_dialog_get_data(self, qt_app):
        """Test getting pairing data from dialog."""
        dialog = ManualPairingDialog()

        dialog._p1_combo.setEditText("Team Alpha")
        dialog._p2_combo.setEditText("Team Beta")
        dialog._board_spin.setValue(5)

        p1, p2, board = dialog.get_data()

        assert p1 == "Team Alpha"
        assert p2 == "Team Beta"
        assert board == 5

    def test_dialog_empty_data(self, qt_app):
        """Test getting empty pairing data."""
        dialog = ManualPairingDialog()

        p1, p2, board = dialog.get_data()

        assert p1 == ""
        assert p2 == ""
        assert board == 1

    def test_dialog_with_participant_names(self, qt_app):
        """Test that dropdown is populated with participant names."""
        names = ["Zara", "Alice", "Morgan", "Bob"]
        dialog = ManualPairingDialog(participant_names=names)

        assert dialog._p1_combo.count() == 4
        assert dialog._p2_combo.count() == 4

        items_p1 = [
            dialog._p1_combo.itemText(i) for i in range(dialog._p1_combo.count())
        ]
        assert items_p1 == sorted(names)

    def test_dialog_select_existing_participant(self, qt_app):
        """Test selecting an existing participant from dropdown."""
        names = ["Team Alpha", "Team Beta"]
        dialog = ManualPairingDialog(participant_names=names)

        dialog._p1_combo.setCurrentText("Team Alpha")
        dialog._p2_combo.setCurrentText("Team Beta")

        p1, p2, board = dialog.get_data()

        assert p1 == "Team Alpha"
        assert p2 == "Team Beta"


# ============================================================================
# MANUAL ENTRY WORKFLOW TESTS
# ============================================================================


class TestOfflineManualWorkflow:
    """Tests for complete offline manual entry workflow."""

    def test_create_offline_tournament(self, qt_app, mock_database_path):
        """Test creating a tournament without URL."""
        with mock_database_path() as db_path:
            _, tournament_id = create_tournament(
                name="No Internet Tournament",
                source_url=None,
                tournament_type="individual",
            )

            assert tournament_id is not None
            assert os.path.exists(db_path)

            session = get_session(db_path)
            from database.models import Tournament

            tournament = session.query(Tournament).first()
            assert tournament.source_url is None
            session.close()

    def test_manual_round_creation(self, offline_tournament):
        """Test manually creating a round with pairings."""
        session = offline_tournament["session"]
        tournament_id = offline_tournament["tournament_id"]

        # Create round data manually
        round_data = RoundData(
            round_number=1,
            pairings=[
                PairingData("Team A", "Team B", board_number=1),
                PairingData("Team C", "Team D", board_number=2),
                PairingData("Team E", "Team F", board_number=3),
            ],
        )

        round_obj = create_round_from_data(session, tournament_id, round_data, "team")

        assert round_obj.round_number == 1

        # Verify pairings were created
        pairings = get_round_pairings(session, round_obj.id)
        assert len(pairings) == 3

    def test_manual_participant_creation(self, offline_tournament):
        """Test that participants are created when adding pairings."""
        session = offline_tournament["session"]
        tournament_id = offline_tournament["tournament_id"]

        # Create round with new participants
        round_data = RoundData(
            round_number=1,
            pairings=[
                PairingData("New Team A", "New Team B", board_number=1),
            ],
        )

        create_round_from_data(session, tournament_id, round_data, "team")

        # Verify participants were created
        from database.queries import get_all_participants

        participants = get_all_participants(session, tournament_id)
        participant_names = [p.name for p in participants]

        assert "New Team A" in participant_names
        assert "New Team B" in participant_names

    def test_multiple_manual_rounds(self, offline_tournament):
        """Test creating multiple rounds manually."""
        session = offline_tournament["session"]
        tournament_id = offline_tournament["tournament_id"]

        # Create 3 rounds manually
        for round_num in range(1, 4):
            round_data = RoundData(
                round_number=round_num,
                pairings=[
                    PairingData("Team A", "Team B", board_number=1),
                    PairingData("Team C", "Team D", board_number=2),
                ],
            )
            create_round_from_data(session, tournament_id, round_data, "team")

        # Verify all rounds exist
        rounds = get_all_rounds(session, tournament_id)
        assert len(rounds) == 3

        # Verify each round has pairings
        for round_obj in rounds:
            pairings = get_round_pairings(session, round_obj.id)
            assert len(pairings) == 2

    def test_full_offline_workflow_with_allocation(self, offline_tournament):
        """Test complete offline workflow: create tournament, add rounds, allocate boards."""
        session = offline_tournament["session"]
        tournament_id = offline_tournament["tournament_id"]

        # Create 3 rounds with pairings
        for round_num in range(1, 4):
            round_data = RoundData(
                round_number=round_num,
                pairings=[
                    PairingData("Team A", "Team B", board_number=1),
                    PairingData("Team C", "Team D", board_number=2),
                    PairingData("Team E", "Team F", board_number=3),
                ],
            )
            create_round_from_data(session, tournament_id, round_data, "team")

        # Allocate digital boards for round 1
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        result = allocate_digital_boards(session, round_obj.id, 2)

        assert len(result) == 2

        # Verify assignments were created
        pairings = get_round_pairings(session, round_obj.id)
        assigned_pairings = [
            p
            for p in pairings
            if p.digital_assignment and p.digital_assignment.digital_board_label
        ]
        assert len(assigned_pairings) == 2

    def test_manual_entry_preserves_on_reallocation(self, offline_tournament):
        """Test that manual assignments are preserved when reallocating."""
        session = offline_tournament["session"]
        tournament_id = offline_tournament["tournament_id"]

        # Create round
        round_data = RoundData(
            round_number=1,
            pairings=[
                PairingData("Team A", "Team B", board_number=1),
                PairingData("Team C", "Team D", board_number=2),
                PairingData("Team E", "Team F", board_number=3),
            ],
        )
        round_obj = create_round_from_data(session, tournament_id, round_data, "team")

        # Auto-allocate
        allocate_digital_boards(session, round_obj.id, 2)

        # Manually change one assignment
        from logic.allocator import manually_assign_digital_board

        pairings = get_round_pairings(session, round_obj.id)
        manually_assign_digital_board(session, pairings[0].id, "Board Z")

        # Reallocate
        allocate_digital_boards(session, round_obj.id, 2)

        # Manual assignment should be preserved
        assert pairings[0].digital_assignment.digital_board_label == "Board Z"
        assert pairings[0].digital_assignment.is_manual == True


# ============================================================================
# GUI MANUAL ENTRY INTEGRATION TESTS
# ============================================================================


class TestGuiManualEntryIntegration:
    """Tests for GUI manual entry integration."""

    @patch("gui.main_window.QMessageBox")
    def test_manual_add_round_from_menu(
        self, mock_messagebox, qt_app, offline_tournament
    ):
        """Test adding a round through the GUI menu."""
        from gui.main_window import MainWindow

        with patch("gui.main_window.ManualRoundDialog") as mock_dialog:
            # Setup mock dialog
            mock_instance = Mock()
            mock_instance.exec.return_value = True
            mock_instance.get_data.return_value = (
                1,  # round number
                [
                    {
                        "participant1": "Team A",
                        "participant2": "Team B",
                        "board_number": 1,
                    },
                    {
                        "participant1": "Team C",
                        "participant2": "Team D",
                        "board_number": 2,
                    },
                ],
            )
            mock_dialog.return_value = mock_instance

            # Create window and load tournament
            window = MainWindow()
            window.db_path = offline_tournament["db_path"]
            window.tournament_id = offline_tournament["tournament_id"]
            window.session = offline_tournament["session"]
            window._load_rounds()
            window._load_participants()

            # Call manual add round
            window._manual_add_round()

            # Verify dialog was called
            mock_dialog.assert_called_once()

            # Verify round was created
            rounds = get_all_rounds(window.session, window.tournament_id)
            assert len(rounds) >= 1

            window.session.close()

    @patch("gui.main_window.QMessageBox")
    def test_manual_entry_menu_items_exist(self, mock_messagebox, qt_app):
        """Test that manual entry menu items exist."""
        from gui.main_window import MainWindow

        window = MainWindow()

        # Check that menu bar exists
        assert window.menuBar() is not None

        # Get the Round menu
        round_menu = None
        for action in window.menuBar().actions():
            if action.menu() and "Round" in action.text():
                round_menu = action.menu()
                break

        assert round_menu is not None

        # Check for manual add round action
        has_manual_add = False
        for action in round_menu.actions():
            if "Manual" in action.text() or "Add Round" in action.text():
                has_manual_add = True
                break

        assert has_manual_add, "Manual add round menu item should exist"


# ============================================================================
# OFFLINE MODE EDGE CASE TESTS
# ============================================================================


class TestOfflineModeEdgeCases:
    """Tests for offline mode edge cases."""

    def test_empty_tournament_manual_add(self, qt_app, mock_database_path):
        """Test adding first round to empty tournament."""
        with mock_database_path() as db_path:
            _, tournament_id = create_tournament("Empty Offline")
            session = get_session(db_path)

            # Tournament should be empty
            rounds = get_all_rounds(session, tournament_id)
            assert len(rounds) == 0

            # Add first round
            round_data = RoundData(
                round_number=1,
                pairings=[PairingData("A", "B", board_number=1)],
            )
            create_round_from_data(session, tournament_id, round_data, "player")

            # Should now have one round
            rounds = get_all_rounds(session, tournament_id)
            assert len(rounds) == 1

            session.close()

    def test_duplicate_round_number(self, offline_tournament):
        """Test adding round with duplicate number overwrites."""
        session = offline_tournament["session"]
        tournament_id = offline_tournament["tournament_id"]

        # Create round 1
        round_data1 = RoundData(
            round_number=1,
            pairings=[PairingData("A", "B", board_number=1)],
        )
        create_round_from_data(session, tournament_id, round_data1, "team")

        # Create round 1 again with different pairings
        round_data2 = RoundData(
            round_number=1,
            pairings=[
                PairingData("C", "D", board_number=1),
                PairingData("E", "F", board_number=2),
            ],
        )
        create_round_from_data(session, tournament_id, round_data2, "team")

        # Should still have only one round with new pairings
        rounds = get_all_rounds(session, tournament_id)
        assert len(rounds) == 1

        pairings = get_round_pairings(session, rounds[0].id)
        assert len(pairings) == 2

    def test_mixed_individual_and_team_names(self, offline_tournament):
        """Test that participant type is respected."""
        session = offline_tournament["session"]
        tournament_id = offline_tournament["tournament_id"]

        round_data = RoundData(
            round_number=1,
            pairings=[
                PairingData("Player A", "Player B", board_number=1),
            ],
        )
        create_round_from_data(session, tournament_id, round_data, "player")

        from database.models import Participant

        participants = session.query(Participant).all()
        assert all(p.participant_type == "player" for p in participants)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
