"""
Broadcast Board Tracker - Test Suite

Comprehensive tests including:
- Unit tests for individual components
- Integration tests for database operations
- GUI tests for manual operations
- Offline mode tests (when scraper is unavailable)
- Manual correction tests
"""

import pytest
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

# Database imports
from database.models import Tournament, Participant, Round, Pairing, DigitalAssignment
from database.init_db import create_database, get_session, create_tournament
from database.queries import (
    get_all_participants,
    get_all_rounds,
    get_round_pairings,
    count_digital_rounds_for_participant,
    get_pairing_digital_sum,
)

# Logic imports
from logic.allocator import (
    allocate_digital_boards,
    clear_round_assignments,
    manually_assign_digital_board,
    exclude_from_digital,
    generate_digital_board_labels,
)
from logic.tournament import (
    ensure_participant_exists,
    create_round_from_data,
    import_rounds_from_data,
    delete_round,
)
from logic.pairing import PairingData, RoundData

# Scraper imports
from scrapers.schack_se import SchackSeScraper

# Utils imports
from utils.export import export_to_csv, export_to_json, export_statistics


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.sqlite")
    create_database("test")

    # Override with our temp path
    from database import init_db

    original_get_path = init_db.get_database_path
    call_counter = [0]  # Use list to allow modification in closure

    def mock_get_path(name):
        call_counter[0] += 1
        if call_counter[0] == 1:
            return db_path
        # For subsequent calls (collision scenario), return different path
        return os.path.join(temp_dir, f"test_{call_counter[0]}.sqlite")

    init_db.get_database_path = mock_get_path

    yield db_path

    # Cleanup
    shutil.rmtree(temp_dir)
    init_db.get_database_path = original_get_path


@pytest.fixture
def test_tournament(temp_db):
    """Create a test tournament with sample data."""
    db_path, tournament_id = create_tournament(
        name="Test Tournament",
        source_url="https://member.schack.se/test",
        tournament_type="team",
    )

    session = get_session(db_path)

    # Create participants
    participants = []
    for name in ["Team A", "Team B", "Team C", "Team D", "Team E", "Team F"]:
        p = Participant(tournament_id=tournament_id, name=name, participant_type="team")
        session.add(p)
        participants.append(p)
    session.commit()

    # Create rounds with pairings
    rounds = []
    for round_num in range(1, 4):
        round_obj = Round(tournament_id=tournament_id, round_number=round_num)
        session.add(round_obj)
    session.commit()

    # Create pairings for each round
    for i, round_obj in enumerate(
        session.query(Round).order_by(Round.round_number).all()
    ):
        pairing1 = Pairing(
            round_id=round_obj.id,
            participant1_id=participants[0].id,
            participant2_id=participants[1].id,
            board_number=i + 1,
        )
        pairing2 = Pairing(
            round_id=round_obj.id,
            participant1_id=participants[2].id,
            participant2_id=participants[3].id,
            board_number=i + 2,
        )
        pairing3 = Pairing(
            round_id=round_obj.id,
            participant1_id=participants[4].id,
            participant2_id=participants[5].id,
            board_number=i + 3,
        )
        session.add(pairing1)
        session.add(pairing2)
        session.add(pairing3)

    session.commit()

    yield {
        "db_path": db_path,
        "tournament_id": tournament_id,
        "session": session,
        "participants": participants,
        "rounds": session.query(Round).all(),
    }

    session.close()


# ============================================================================
# UNIT TESTS - Allocator
# ============================================================================


class TestDigitalBoardLabels:
    """Tests for digital board label generation."""

    def test_generate_labels_single_digit(self):
        """Test generating labels for 1-9 boards."""
        labels = generate_digital_board_labels(5)
        assert labels == ["Board A", "Board B", "Board C", "Board D", "Board E"]

    def test_generate_labels_custom_prefix(self):
        """Test generating labels with custom prefix."""
        labels = generate_digital_board_labels(3, prefix="Digital")
        assert labels == ["Digital A", "Digital B", "Digital C"]

    def test_generate_labels_zero_boards(self):
        """Test generating labels for zero boards."""
        labels = generate_digital_board_labels(0)
        assert labels == []

    def test_generate_labels_many_boards(self):
        """Test generating labels for more than 26 boards."""
        labels = generate_digital_board_labels(30)
        assert len(labels) == 30
        assert labels[0] == "Board A"
        assert labels[25] == "Board Z"


class TestAllocationAlgorithm:
    """Tests for the digital board allocation algorithm."""

    def test_allocates_to_lowest_counts(self, test_tournament):
        """Test that boards are allocated to pairings with lowest combined counts."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()

        # Allocate 2 boards
        result = allocate_digital_boards(session, round_obj.id, 2)

        assert len(result) == 2

        # All participants should have 0 count initially, so any 2 should be selected
        for pairing, label in result:
            assignment = pairing.digital_assignment
            assert assignment is not None
            assert assignment.digital_board_label is not None
            assert assignment.is_manual == False

    def test_respects_manual_assignments(self, test_tournament):
        """Test that manual assignments are preserved during allocation."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()

        # Manually assign first pairing
        pairings = get_round_pairings(session, round_obj.id)
        manually_assign_digital_board(session, pairings[0].id, "Board A")

        # Allocate boards
        allocate_digital_boards(session, round_obj.id, 3)

        # Manual assignment should be preserved
        assignment = pairings[0].digital_assignment
        assert assignment.digital_board_label == "Board A"
        assert assignment.is_manual == True

    def test_random_tiebreaking(self, test_tournament):
        """Test that ties are broken randomly."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()

        # With all counts at 0, selection should be random
        # Run multiple times to verify randomness
        selected_pairings = set()
        for _ in range(10):
            clear_round_assignments(session, round_obj.id)
            result = allocate_digital_boards(session, round_obj.id, 2)
            for pairing, _ in result:
                selected_pairings.add(pairing.id)

        # Should have selected more than 2 unique pairings across runs
        assert len(selected_pairings) > 2


# ============================================================================
# UNIT TESTS - Manual Operations
# ============================================================================


class TestManualAssignment:
    """Tests for manual digital board assignment."""

    def test_assign_board(self, test_tournament):
        """Test manually assigning a digital board."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round_obj.id)

        assignment = manually_assign_digital_board(session, pairings[0].id, "Board A")

        assert assignment.digital_board_label == "Board A"
        assert assignment.is_manual == True
        assert assignment.is_excluded == False

    def test_remove_assignment(self, test_tournament):
        """Test removing a digital board assignment."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round_obj.id)

        # First assign
        manually_assign_digital_board(session, pairings[0].id, "Board A")

        # Then remove
        assignment = manually_assign_digital_board(session, pairings[0].id, None)

        assert assignment.digital_board_label is None
        assert assignment.is_manual == True

    def test_overwrite_auto_with_manual(self, test_tournament):
        """Test overwriting auto assignment with manual."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round_obj.id)

        # Auto allocate
        allocate_digital_boards(session, round_obj.id, 3)

        # Manually change one
        manually_assign_digital_board(session, pairings[0].id, "Board Z")

        assignment = pairings[0].digital_assignment
        assert assignment.digital_board_label == "Board Z"
        assert assignment.is_manual == True


class TestExcludeFromDigital:
    """Tests for excluding pairings from digital boards."""

    def test_exclude_pairing(self, test_tournament):
        """Test excluding a pairing from digital board consideration."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round_obj.id)

        assignment = exclude_from_digital(session, pairings[0].id, True)

        assert assignment.is_excluded == True
        assert assignment.digital_board_label is None

    def test_include_pairing(self, test_tournament):
        """Test including a previously excluded pairing."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round_obj.id)

        # Exclude first
        exclude_from_digital(session, pairings[0].id, True)

        # Then include
        assignment = exclude_from_digital(session, pairings[0].id, False)

        assert assignment.is_excluded == False

    def test_excluded_not_counted(self, test_tournament):
        """Test that excluded assignments don't count toward digital round count."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round_obj.id)

        # Assign and then exclude
        manually_assign_digital_board(session, pairings[0].id, "Board A")
        exclude_from_digital(session, pairings[0].id, True)

        # Count should be 0
        count = count_digital_rounds_for_participant(
            session, pairings[0].participant1_id
        )
        assert count == 0


class TestClearAssignments:
    """Tests for clearing round assignments."""

    def test_clear_all_assignments(self, test_tournament):
        """Test clearing all assignments for a round."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()

        # Create some assignments
        pairings = get_round_pairings(session, round_obj.id)
        manually_assign_digital_board(session, pairings[0].id, "Board A")
        manually_assign_digital_board(session, pairings[1].id, "Board B")

        # Clear
        count = clear_round_assignments(session, round_obj.id)

        assert count == 2

        # Verify cleared
        for pairing in pairings:
            assert pairing.digital_assignment is None

    def test_clear_empty_round(self, test_tournament):
        """Test clearing a round with no assignments."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 2).first()

        count = clear_round_assignments(session, round_obj.id)

        assert count == 0


# ============================================================================
# INTEGRATION TESTS - Tournament Management
# ============================================================================


class TestTournamentCreation:
    """Tests for tournament creation and management."""

    def test_create_tournament(self, temp_db):
        """Test creating a new tournament."""
        db_path, tournament_id = create_tournament(
            name="New Tournament",
            source_url="https://example.com",
            tournament_type="individual",
        )

        assert tournament_id is not None
        assert os.path.exists(db_path)

        session = get_session(db_path)
        tournament = session.query(Tournament).first()

        assert tournament.name == "New Tournament"
        assert tournament.tournament_type == "individual"
        session.close()

    def test_create_tournament_collision_handling(self, temp_db):
        """Test that duplicate tournament names get unique filenames."""
        db_path1, _ = create_tournament("Same Name")
        db_path2, _ = create_tournament("Same Name")

        assert db_path1 != db_path2
        assert os.path.exists(db_path1)
        assert os.path.exists(db_path2)


class TestParticipantManagement:
    """Tests for participant management."""

    def test_ensure_participant_exists_new(self, test_tournament):
        """Test creating a new participant."""
        session = test_tournament["session"]
        tournament_id = test_tournament["tournament_id"]

        participant = ensure_participant_exists(
            session, tournament_id, "New Team", "team"
        )

        assert participant.name == "New Team"
        assert participant.participant_type == "team"

    def test_ensure_participant_exists_existing(self, test_tournament):
        """Test getting existing participant."""
        session = test_tournament["session"]
        tournament_id = test_tournament["tournament_id"]

        original = test_tournament["participants"][0]
        participant = ensure_participant_exists(
            session, tournament_id, original.name, "team"
        )

        assert participant.id == original.id

    def test_no_duplicate_participants(self, test_tournament):
        """Test that duplicate participants are not created."""
        session = test_tournament["session"]
        tournament_id = test_tournament["tournament_id"]

        ensure_participant_exists(session, tournament_id, "Duplicate", "team")
        ensure_participant_exists(session, tournament_id, "Duplicate", "team")

        participants = (
            session.query(Participant).filter(Participant.name == "Duplicate").all()
        )

        assert len(participants) == 1


class TestRoundManagement:
    """Tests for round management."""

    def test_create_round_from_data(self, test_tournament):
        """Test creating a round from RoundData."""
        session = test_tournament["session"]
        tournament_id = test_tournament["tournament_id"]

        pairings = [
            PairingData("Team X", "Team Y", board_number=1),
            PairingData("Team Z", "Team W", board_number=2),
        ]
        round_data = RoundData(round_number=5, pairings=pairings)

        round_obj = create_round_from_data(session, tournament_id, round_data, "team")

        assert round_obj.round_number == 5

        round_pairings = get_round_pairings(session, round_obj.id)
        assert len(round_pairings) == 2

    def test_import_multiple_rounds(self, test_tournament):
        """Test importing multiple rounds at once."""
        session = test_tournament["session"]
        tournament_id = test_tournament["tournament_id"]

        rounds_data = [
            RoundData(
                round_number=6, pairings=[PairingData("A", "B"), PairingData("C", "D")]
            ),
            RoundData(
                round_number=7, pairings=[PairingData("E", "F"), PairingData("G", "H")]
            ),
        ]

        created_rounds = import_rounds_from_data(
            session, tournament_id, rounds_data, "team"
        )

        assert len(created_rounds) == 2

    def test_delete_round(self, test_tournament):
        """Test deleting a round and its data."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 3).first()

        # Add an assignment to test cascade delete
        pairings = get_round_pairings(session, round_obj.id)
        manually_assign_digital_board(session, pairings[0].id, "Board A")

        result = delete_round(session, round_obj.id)

        assert result == True

        # Verify deleted
        deleted_round = session.query(Round).filter(Round.id == round_obj.id).first()
        assert deleted_round is None


# ============================================================================
# INTEGRATION TESTS - Digital Round Counting
# ============================================================================


class TestDigitalRoundCounting:
    """Tests for digital round counting logic."""

    def test_count_increments_correctly(self, test_tournament):
        """Test that digital round count increments correctly."""
        session = test_tournament["session"]
        participants = test_tournament["participants"]

        # Initially should be 0
        count = count_digital_rounds_for_participant(session, participants[0].id)
        assert count == 0

        # Assign in round 1
        round1 = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round1.id)
        manually_assign_digital_board(session, pairings[0].id, "Board A")

        # Should be 1
        count = count_digital_rounds_for_participant(session, participants[0].id)
        assert count == 1

        # Assign in round 2
        round2 = session.query(Round).filter(Round.round_number == 2).first()
        pairings = get_round_pairings(session, round2.id)
        manually_assign_digital_board(session, pairings[0].id, "Board A")

        # Should be 2
        count = count_digital_rounds_for_participant(session, participants[0].id)
        assert count == 2

    def test_pairing_digital_sum(self, test_tournament):
        """Test calculating combined digital count for a pairing."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round_obj.id)

        # Initially should be 0
        total = get_pairing_digital_sum(session, pairings[0])
        assert total == 0

        # Assign both participants in other rounds
        manually_assign_digital_board(session, pairings[0].id, "Board A")

        # Now both participants have 1
        total = get_pairing_digital_sum(session, pairings[0])
        assert total == 2


# ============================================================================
# OFFLINE MODE TESTS - Manual Data Entry
# ============================================================================


class TestOfflineMode:
    """Tests for offline mode when scraper is unavailable."""

    def test_create_tournament_without_url(self, temp_db):
        """Test creating a tournament without a source URL."""
        db_path, tournament_id = create_tournament(
            name="Offline Tournament", source_url=None, tournament_type="individual"
        )

        session = get_session(db_path)
        tournament = session.query(Tournament).first()

        assert tournament.source_url is None
        session.close()

    def test_manual_pairing_entry(self, temp_db):
        """Test manually entering pairings without scraper."""
        db_path, tournament_id = create_tournament("Manual Entry")
        session = get_session(db_path)

        # Manually create participants
        for name in ["Player A", "Player B", "Player C", "Player D"]:
            ensure_participant_exists(session, tournament_id, name, "player")

        # Manually create round with pairings
        round_data = RoundData(
            round_number=1,
            pairings=[
                PairingData("Player A", "Player B", board_number=1),
                PairingData("Player C", "Player D", board_number=2),
            ],
        )

        created_round = create_round_from_data(
            session, tournament_id, round_data, "player"
        )

        pairings = get_round_pairings(session, created_round.id)
        assert len(pairings) == 2

        session.close()

    def test_full_manual_workflow(self, temp_db):
        """Test complete manual workflow from tournament creation to allocation."""
        db_path, tournament_id = create_tournament("Full Manual")
        session = get_session(db_path)

        # Create 6 participants
        for i in range(1, 7):
            ensure_participant_exists(session, tournament_id, f"Player {i}", "player")

        # Create 3 rounds with pairings
        for round_num in range(1, 4):
            round_data = RoundData(
                round_number=round_num,
                pairings=[
                    PairingData(
                        f"Player {1 + (round_num - 1) * 2}",
                        f"Player {2 + (round_num - 1) * 2}",
                    ),
                    PairingData(
                        f"Player {3 + (round_num - 1) * 2}",
                        f"Player {4 + (round_num - 1) * 2}",
                    ),
                    PairingData(
                        f"Player {5 + (round_num - 1) * 2}",
                        f"Player {6 + (round_num - 1) * 2}",
                    ),
                ],
            )
            create_round_from_data(session, tournament_id, round_data, "player")

        # Allocate digital boards for round 1
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        result = allocate_digital_boards(session, round_obj.id, 2)

        assert len(result) == 2

        session.close()


# ============================================================================
# SCRAPER TESTS - With Mocking
# ============================================================================


class TestScraperOffline:
    """Tests for scraper behavior when offline."""

    def test_scraper_handles_network_error(self):
        """Test that scraper handles network errors gracefully."""
        scraper = SchackSeScraper()

        with patch.object(
            scraper.session, "get", side_effect=Exception("Network error")
        ):
            with pytest.raises(Exception):
                scraper.fetch_tournament_url("https://example.com")

    def test_scraper_handles_timeout(self):
        """Test that scraper handles timeouts gracefully."""
        from requests import Timeout

        scraper = SchackSeScraper()

        with patch.object(scraper.session, "get", side_effect=Timeout()):
            with pytest.raises(Timeout):
                scraper.fetch_tournament_url("https://example.com")

    def test_scraper_handles_invalid_html(self):
        """Test that scraper handles invalid HTML gracefully."""
        scraper = SchackSeScraper()

        # Empty HTML
        rounds = scraper.parse_rounds("")
        assert rounds == []

        # Invalid HTML
        rounds = scraper.parse_rounds("<html>invalid</html>")
        assert isinstance(rounds, list)


class TestScraperParsing:
    """Tests for scraper parsing logic."""

    def test_parse_tournament_name(self):
        """Test parsing tournament name from HTML."""
        scraper = SchackSeScraper()

        html = """
        <html>
        <h4 class="header">Test Tournament Name</h4>
        </html>
        """

        name = scraper.parse_tournament_name(html)
        assert name == "Test Tournament Name"

    def test_parse_tournament_name_fallback(self):
        """Test parsing tournament name fallback to title."""
        scraper = SchackSeScraper()

        html = """
        <html>
        <title>Fallback Tournament</title>
        </html>
        """

        name = scraper.parse_tournament_name(html)
        assert name == "Fallback Tournament"

    def test_parse_rounds(self):
        """Test parsing round numbers from HTML."""
        scraper = SchackSeScraper()

        html = """
        <html>
        <a href="/ShowTournamentGroupMatchesServlet?id=123&round=1">Round 1</a>
        <a href="/ShowTournamentGroupMatchesServlet?id=123&round=2">Round 2</a>
        <a href="/ShowTournamentGroupMatchesServlet?id=123&round=3">Round 3</a>
        </html>
        """

        rounds = scraper.parse_rounds(html)
        assert rounds == [1, 2, 3]

    def test_parse_pairings(self):
        """Test parsing pairings from round HTML."""
        scraper = SchackSeScraper()

        html = """
        <table class="greyproptable">
        <tr>
            <td class="listheader">Team A</td>
            <td class="listheader">Team B</td>
            <td class="listheadercenter">3 - 1</td>
        </tr>
        </table>
        """

        pairings = scraper.parse_round_pairings(html, 1)

        assert len(pairings) == 1
        assert pairings[0]["participant1"] == "Team A"
        assert pairings[0]["participant2"] == "Team B"
        assert pairings[0]["score1"] == 3.0
        assert pairings[0]["score2"] == 1.0

    def test_parse_fractional_scores(self):
        """Test parsing fractional scores like 3½ - ½."""
        scraper = SchackSeScraper()

        html = """
        <table class="greyproptable">
        <tr>
            <td class="listheader">Team A</td>
            <td class="listheader">Team B</td>
            <td class="listheadercenter">3½ - ½</td>
        </tr>
        </table>
        """

        pairings = scraper.parse_round_pairings(html, 1)

        assert pairings[0]["score1"] == 3.5
        assert pairings[0]["score2"] == 0.5


# ============================================================================
# EXPORT TESTS
# ============================================================================


class TestExportCSV:
    """Tests for CSV export functionality."""

    def test_export_csv(self, test_tournament):
        """Test exporting tournament data to CSV."""
        session = test_tournament["session"]
        tournament_id = test_tournament["tournament_id"]

        # Add some assignments
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round_obj.id)
        manually_assign_digital_board(session, pairings[0].id, "Board A")

        # Export
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            output_path = f.name

        try:
            result_path = export_to_csv(session, tournament_id, output_path)

            assert os.path.exists(result_path)

            # Read and verify
            with open(result_path, "r") as f:
                content = f.read()
                assert "Test Tournament" in content
                assert "Board A" in content
        finally:
            if os.path.exists(result_path):
                os.remove(result_path)

    def test_export_csv_collision_handling(self, test_tournament):
        """Test CSV export handles filename collisions."""
        session = test_tournament["session"]
        tournament_id = test_tournament["tournament_id"]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            output_path = f.name

        try:
            # First export
            result_path1 = export_to_csv(session, tournament_id, output_path)

            # Second export to same path
            result_path2 = export_to_csv(session, tournament_id, output_path)

            # Should create unique filename
            assert result_path1 != result_path2
            assert os.path.exists(result_path2)

            if os.path.exists(result_path2):
                os.remove(result_path2)
        finally:
            if os.path.exists(result_path1):
                os.remove(result_path1)


class TestExportJSON:
    """Tests for JSON export functionality."""

    def test_export_json(self, test_tournament):
        """Test exporting tournament data to JSON."""
        session = test_tournament["session"]
        tournament_id = test_tournament["tournament_id"]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_path = f.name

        try:
            result_path = export_to_json(session, tournament_id, output_path)

            assert os.path.exists(result_path)

            # Read and verify
            import json

            with open(result_path, "r") as f:
                data = json.load(f)

                assert data["tournament"]["name"] == "Test Tournament"
                assert len(data["rounds"]) == 3
        finally:
            if os.path.exists(result_path):
                os.remove(result_path)


class TestExportStatistics:
    """Tests for statistics export functionality."""

    def test_export_statistics(self, test_tournament):
        """Test exporting digital board statistics."""
        session = test_tournament["session"]
        tournament_id = test_tournament["tournament_id"]

        # Add some assignments
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round_obj.id)
        manually_assign_digital_board(session, pairings[0].id, "Board A")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            output_path = f.name

        try:
            result_path = export_statistics(session, tournament_id, output_path)

            assert os.path.exists(result_path)

            # Read and verify
            with open(result_path, "r") as f:
                content = f.read()
                assert "participant" in content
                assert "digital_rounds" in content
        finally:
            if os.path.exists(result_path):
                os.remove(result_path)


# ============================================================================
# MANUAL CORRECTION TESTS
# ============================================================================


class TestManualCorrections:
    """Tests for all manual correction possibilities."""

    def test_correct_previous_round(self, test_tournament):
        """Test correcting assignments in a previous round."""
        session = test_tournament["session"]

        # Allocate round 1
        round1 = session.query(Round).filter(Round.round_number == 1).first()
        allocate_digital_boards(session, round1.id, 2)

        # Allocate round 2
        round2 = session.query(Round).filter(Round.round_number == 2).first()
        allocate_digital_boards(session, round2.id, 2)

        # Now correct round 1
        pairings = get_round_pairings(session, round1.id)

        # Remove assignment from first pairing
        manually_assign_digital_board(session, pairings[0].id, None)

        # Assign to third pairing instead
        manually_assign_digital_board(session, pairings[2].id, "Board C")

        # Verify corrections
        assert pairings[0].digital_assignment.digital_board_label is None
        assert pairings[2].digital_assignment.digital_board_label == "Board C"

    def test_reallocate_after_correction(self, test_tournament):
        """Test reallocating after manual corrections."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round_obj.id)

        # Manual assignment
        manually_assign_digital_board(session, pairings[0].id, "Board A")

        # Clear and reallocate
        clear_round_assignments(session, round_obj.id)
        allocate_digital_boards(session, round_obj.id, 2)

        # Should have 2 auto assignments
        assigned = [
            p
            for p in pairings
            if p.digital_assignment and p.digital_assignment.digital_board_label
        ]
        assert len(assigned) == 2

    def test_toggle_exclude_multiple_times(self, test_tournament):
        """Test toggling exclude status multiple times."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round_obj.id)

        # Exclude
        exclude_from_digital(session, pairings[0].id, True)
        assert pairings[0].digital_assignment.is_excluded == True

        # Include
        exclude_from_digital(session, pairings[0].id, False)
        assert pairings[0].digital_assignment.is_excluded == False

        # Exclude again
        exclude_from_digital(session, pairings[0].id, True)
        assert pairings[0].digital_assignment.is_excluded == True

    def test_assign_then_exclude(self, test_tournament):
        """Test assigning a board then excluding."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round_obj.id)

        # Assign
        manually_assign_digital_board(session, pairings[0].id, "Board A")
        assert pairings[0].digital_assignment.digital_board_label == "Board A"

        # Exclude (should clear assignment)
        exclude_from_digital(session, pairings[0].id, True)
        assert pairings[0].digital_assignment.digital_board_label is None
        assert pairings[0].digital_assignment.is_excluded == True

    def test_change_manual_assignment(self, test_tournament):
        """Test changing a manual assignment to a different board."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()
        pairings = get_round_pairings(session, round_obj.id)

        # Assign to Board A
        manually_assign_digital_board(session, pairings[0].id, "Board A")

        # Change to Board Z
        manually_assign_digital_board(session, pairings[0].id, "Board Z")

        assert pairings[0].digital_assignment.digital_board_label == "Board Z"
        assert pairings[0].digital_assignment.is_manual == True

    def test_correct_wrong_participant_entry(self, test_tournament):
        """Test correcting wrong participant name entry."""
        session = test_tournament["session"]
        tournament_id = test_tournament["tournament_id"]

        # Create round with wrong name
        round_data = RoundData(
            round_number=4, pairings=[PairingData("Wrong Name", "Team B")]
        )
        round_obj = create_round_from_data(session, tournament_id, round_data, "team")

        # Get the wrong participant and delete
        wrong_participant = (
            session.query(Participant).filter(Participant.name == "Wrong Name").first()
        )

        # Update to correct name
        wrong_participant.name = "Correct Name"
        session.commit()

        # Verify
        correct_participant = (
            session.query(Participant)
            .filter(Participant.name == "Correct Name")
            .first()
        )
        assert correct_participant is not None


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_allocate_more_boards_than_pairings(self, test_tournament):
        """Test allocating more boards than there are pairings."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()

        # Only 3 pairings, request 10 boards
        result = allocate_digital_boards(session, round_obj.id, 10)

        # Should only assign to 3 pairings
        assigned = [
            p
            for p in round_obj.pairings
            if p.digital_assignment and p.digital_assignment.digital_board_label
        ]
        assert len(assigned) == 3

    def test_allocate_zero_boards(self, test_tournament):
        """Test allocating zero boards."""
        session = test_tournament["session"]
        round_obj = session.query(Round).filter(Round.round_number == 1).first()

        result = allocate_digital_boards(session, round_obj.id, 0)

        assert len(result) == 0

    def test_empty_tournament(self, temp_db):
        """Test operations on empty tournament."""
        db_path, tournament_id = create_tournament("Empty")
        session = get_session(db_path)

        # Get rounds should return empty list
        rounds = get_all_rounds(session, tournament_id)
        assert len(rounds) == 0

        # Get participants should return empty list
        participants = get_all_participants(session, tournament_id)
        assert len(participants) == 0

        session.close()

    def test_single_participant(self, temp_db):
        """Test tournament with single participant."""
        db_path, tournament_id = create_tournament("Single")
        session = get_session(db_path)

        ensure_participant_exists(session, tournament_id, "Only One", "player")

        participants = get_all_participants(session, tournament_id)
        assert len(participants) == 1

        session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
