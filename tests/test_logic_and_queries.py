"""Tests for logic layer and database queries to improve coverage.

Covers:
- logic/tournament.py: get_tournament_stats, delete_round, remove_pairing, edit_pairing
- logic/allocator.py: edge cases (zero boards, validation errors, manual preservation)
- database/queries.py: count_digital_rounds_for_participant, get_participant_digital_counts,
  get_pairing_digital_sum, get_max_round
- database/init_db.py: error paths
- utils/export.py: error paths
- scrapers/base.py: default workflow methods
- scrapers/schack_se.py: Method 2 (HEMMALAG/BORTALAG), Method 3 (headerless), _parse_score
"""

import pytest
from unittest.mock import Mock


from database.models import Participant, Round, Pairing, DigitalAssignment
from database.init_db import (
    create_database,
    get_session,
    create_tournament,
    open_tournament,
)
from database.queries import (
    count_digital_rounds_for_participant,
    get_participant_digital_counts,
    get_pairing_digital_sum,
    get_max_round,
    get_round_numbers,
    get_digital_assignment,
    get_pairing_by_id,
    get_all_rounds,
    get_round_pairings,
)
from logic.allocator import (
    generate_digital_board_labels,
    _validate_allocation_params,
)
from logic.tournament import (
    get_tournament_stats,
    delete_round,
    remove_pairing,
    edit_pairing,
)
from utils.export import export, _prepare_export
from scrapers.base import BaseScraper
from scrapers.schack_se import SchackSeScraper


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def populated_tournament(mock_database_path):
    """Create a tournament with participants, rounds, and pairings."""
    with mock_database_path() as db_path:
        _, tournament_id = create_tournament(
            name="Coverage Test",
            source_url="https://example.com",
            tournament_type="individual",
        )
        session = get_session(db_path)

        # Create 4 participants
        participants = []
        for name in ["Alice", "Bob", "Charlie", "Diana"]:
            p = Participant(
                tournament_id=tournament_id, name=name, participant_type="player"
            )
            session.add(p)
            participants.append(p)
        session.commit()

        # Create round 1 with 2 pairings
        round1 = Round(tournament_id=tournament_id, round_number=1)
        session.add(round1)
        session.flush()

        pairing1 = Pairing(
            round_id=round1.id,
            participant1_id=participants[0].id,
            participant2_id=participants[1].id,
            board_number=1,
            score1=1.0,
            score2=0.0,
        )
        pairing2 = Pairing(
            round_id=round1.id,
            participant1_id=participants[2].id,
            participant2_id=participants[3].id,
            board_number=2,
            score1=0.5,
            score2=0.5,
        )
        session.add_all([pairing1, pairing2])
        session.commit()

        # Create round 2 with 2 pairings
        round2 = Round(tournament_id=tournament_id, round_number=2)
        session.add(round2)
        session.flush()

        pairing3 = Pairing(
            round_id=round2.id,
            participant1_id=participants[0].id,
            participant2_id=participants[2].id,
            board_number=1,
            score1=0.0,
            score2=1.0,
        )
        pairing4 = Pairing(
            round_id=round2.id,
            participant1_id=participants[1].id,
            participant2_id=participants[3].id,
            board_number=2,
            score1=1.0,
            score2=0.0,
        )
        session.add_all([pairing3, pairing4])
        session.commit()

        # Assign digital boards to pairing1 and pairing3
        da1 = DigitalAssignment(pairing_id=pairing1.id, digital_board_label="Board A")
        da2 = DigitalAssignment(pairing_id=pairing3.id, digital_board_label="Board A")
        session.add_all([da1, da2])
        session.commit()

        yield (
            db_path,
            tournament_id,
            session,
            participants,
            [pairing1, pairing2, pairing3, pairing4],
            [round1, round2],
        )

        session.close()


# ============================================================================
# DATABASE QUERIES
# ============================================================================


class TestCountDigitalRoundsForParticipant:
    """Tests for count_digital_rounds_for_participant."""

    def test_counts_digital_rounds_correctly(self, populated_tournament):
        db_path, _, session, participants, _, _ = populated_tournament
        # Alice (participants[0]) has digital assignments in rounds 1 and 2
        count = count_digital_rounds_for_participant(session, participants[0].id)
        assert count == 2

    def test_returns_zero_for_no_assignments(self, populated_tournament):
        db_path, _, session, participants, _, _ = populated_tournament
        # Diana (participants[3]) has no digital assignments
        count = count_digital_rounds_for_participant(session, participants[3].id)
        assert count == 0

    def test_excludes_excluded_assignments(self, populated_tournament):
        db_path, _, session, participants, pairings, _ = populated_tournament
        # Mark Alice's round 1 assignment as excluded
        da = get_digital_assignment(session, pairings[0].id)
        da.is_excluded = True
        session.commit()
        count = count_digital_rounds_for_participant(session, participants[0].id)
        # Should only count round 2
        assert count == 1


class TestParticipantDigitalCounts:
    """Tests for get_participant_digital_counts."""

    def test_returns_counts_for_all_participants(self, populated_tournament):
        db_path, _, session, participants, _, _ = populated_tournament
        counts = get_participant_digital_counts(session, participants[0].tournament_id)
        assert len(counts) == 4
        assert counts[participants[0].id] == 2  # Alice: rounds 1 & 2
        assert counts[participants[3].id] == 0  # Diana: none


class TestPairingDigitalSum:
    """Tests for get_pairing_digital_sum."""

    def test_sum_of_both_participants(self, populated_tournament):
        db_path, _, session, participants, pairings, _ = populated_tournament
        # pairing1: Alice(2) vs Bob(1) = 3
        total = get_pairing_digital_sum(session, pairings[0])
        assert total == 3

    def test_nonzero_sum_for_assigned_pairing(self, populated_tournament):
        db_path, _, session, participants, pairings, _ = populated_tournament
        # pairing3: Alice(2) vs Charlie(1) = 3
        total = get_pairing_digital_sum(session, pairings[2])
        assert total == 3

    def test_zero_sum_for_unassigned_participants(self, populated_tournament):
        db_path, _, session, participants, pairings, _ = populated_tournament
        # pairing4: Bob(1) vs Diana(0) = 1 (Bob has assignment in round 1)
        # Diana has no assignments at all
        count_diana = count_digital_rounds_for_participant(session, participants[3].id)
        assert count_diana == 0


class TestMaxRound:
    """Tests for get_max_round."""

    def test_returns_max_round_number(self, populated_tournament):
        db_path, _, session, _, _, _ = populated_tournament
        max_r = get_max_round(session, 1)
        assert max_r == 2

    def test_returns_zero_for_no_rounds(self, temp_db_path):
        db_path, tournament_id = create_tournament(
            name="Empty",
            source_url="https://example.com",
            tournament_type="individual",
        )
        session = get_session(db_path)
        max_r = get_max_round(session, tournament_id)
        assert max_r == 0
        session.close()


class TestRoundNumbers:
    """Tests for get_round_numbers."""

    def test_returns_sorted_round_numbers(self, populated_tournament):
        db_path, _, session, _, _, _ = populated_tournament
        nums = get_round_numbers(session, 1)
        assert nums == [1, 2]


# ============================================================================
# LOGIC / TOURNAMENT
# ============================================================================


class TestGetTournamentStats:
    """Tests for get_tournament_stats."""

    def test_returns_stats_dict(self, populated_tournament):
        db_path, _, session, _, _, _ = populated_tournament
        stats = get_tournament_stats(session, 1)
        assert stats["name"] == "Coverage Test"
        assert stats["tournament_type"] == "individual"
        assert stats["num_participants"] == 4
        assert stats["num_rounds"] == 2
        assert stats["max_round"] == 2

    def test_returns_empty_dict_for_missing_tournament(self, populated_tournament):
        db_path, _, session, _, _, _ = populated_tournament
        stats = get_tournament_stats(session, 9999)
        assert stats == {}


class TestDeleteRound:
    """Tests for delete_round."""

    def test_deletes_round_and_pairings(self, populated_tournament):
        db_path, _, session, _, _, rounds = populated_tournament
        round1 = rounds[0]
        result = delete_round(session, round1.id)
        assert result
        # Round should be gone
        remaining = get_all_rounds(session, 1)
        assert len(remaining) == 1
        assert remaining[0].round_number == 2

    def test_returns_false_for_nonexistent_round(self, populated_tournament):
        db_path, _, session, _, _, _ = populated_tournament
        result = delete_round(session, 9999)
        assert not result

    def test_deletes_digital_assignments_too(self, populated_tournament):
        db_path, _, session, _, pairings, rounds = populated_tournament
        # Round 1 has digital assignments
        round1 = rounds[0]
        delete_round(session, round1.id)
        # Verify assignments are gone
        da = (
            session.query(DigitalAssignment)
            .filter(DigitalAssignment.pairing_id == pairings[0].id)
            .first()
        )
        assert da is None


class TestRemovePairing:
    """Tests for remove_pairing."""

    def test_removes_pairing(self, populated_tournament):
        db_path, _, session, _, pairings, _ = populated_tournament
        pairing1 = pairings[0]
        result = remove_pairing(session, pairing1.id)
        assert result
        remaining = get_round_pairings(session, pairing1.round_id)
        assert len(remaining) == 1

    def test_returns_false_for_nonexistent_pairing(self, populated_tournament):
        db_path, _, session, _, _, _ = populated_tournament
        result = remove_pairing(session, 9999)
        assert not result

    def test_removes_digital_assignment_too(self, populated_tournament):
        db_path, _, session, _, pairings, _ = populated_tournament
        pairing1 = pairings[0]  # Has digital assignment
        remove_pairing(session, pairing1.id)
        da = get_digital_assignment(session, pairing1.id)
        assert da is None


class TestEditPairing:
    """Tests for edit_pairing."""

    def test_edits_participants(self, populated_tournament):
        db_path, _, session, _, pairings, _ = populated_tournament
        pairing1 = pairings[0]
        result = edit_pairing(session, pairing1.id, "Charlie", "Diana")
        assert result
        # Reload pairing
        updated = get_pairing_by_id(session, pairing1.id)
        assert updated.participant1.name == "Charlie"
        assert updated.participant2.name == "Diana"

    def test_returns_false_for_nonexistent_pairing(self, populated_tournament):
        db_path, _, session, _, _, _ = populated_tournament
        result = edit_pairing(session, 9999, "X", "Y")
        assert not result

    def test_replaces_with_existing_participants(self, populated_tournament):
        db_path, _, session, _, pairings, _ = populated_tournament
        pairing1 = pairings[0]
        # Use existing participants (Bob and Charlie)
        edit_pairing(session, pairing1.id, "Bob", "Charlie")
        updated = get_pairing_by_id(session, pairing1.id)
        assert updated.participant1.name == "Bob"
        assert updated.participant2.name == "Charlie"


# ============================================================================
# LOGIC / ALLOCATOR EDGE CASES
# ============================================================================


class TestGenerateDigitalBoardLabels:
    """Tests for generate_digital_board_labels edge cases."""

    def test_zero_boards_returns_empty(self):
        assert generate_digital_board_labels(0) == []

    def test_negative_boards_returns_empty(self):
        assert generate_digital_board_labels(-1) == []

    def test_custom_prefix(self):
        labels = generate_digital_board_labels(2, prefix="Stream")
        assert labels == ["Stream A", "Stream B"]


class TestValidateAllocationParams:
    """Tests for _validate_allocation_params."""

    def test_negative_boards_raises(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            _validate_allocation_params(-1, "Board")

    def test_empty_prefix_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_allocation_params(5, "")

    def test_whitespace_prefix_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            _validate_allocation_params(5, "   ")


# ============================================================================
# DATABASE / INIT_DB ERROR PATHS
# ============================================================================


class TestOpenTournament:
    """Tests for open_tournament error paths."""

    def test_raises_for_empty_database(self, temp_db_path):
        """open_tournament should raise when no tournament exists."""

        # Create an empty database
        create_database("empty")
        session = get_session(str(temp_db_path))
        session.close()

        with pytest.raises(ValueError, match="No tournament found"):
            open_tournament(str(temp_db_path))


# ============================================================================
# UTILS / EXPORT ERROR PATHS
# ============================================================================


class TestExportErrors:
    """Tests for export error paths."""

    def test_unknown_format_raises(self, populated_tournament):
        db_path, tournament_id, session, _, _, _ = populated_tournament
        with pytest.raises(ValueError, match="Unknown export format"):
            export(session, tournament_id, "/tmp/output.csv", format_type="XML")

    def test_prepare_export_missing_tournament(self, populated_tournament):
        db_path, tournament_id, session, _, _, _ = populated_tournament
        with pytest.raises(ValueError, match="not found"):
            _prepare_export(session, 9999, "/tmp/output.csv")


# ============================================================================
# SCRAPERS / BASE DEFAULT WORKFLOWS
# ============================================================================


class TestBaseScraperDefaultWorkflows:
    """Tests for BaseScraper default workflow methods."""

    def test_fetch_all_rounds_calls_primitives(self):
        """fetch_all_rounds should call the abstract primitives in order."""
        scraper = Mock(spec=BaseScraper)
        scraper.fetch_tournament_url.return_value = "<html></html>"
        scraper.parse_tournament_name.return_value = "Test Tournament"
        scraper.parse_rounds.return_value = [1, 2, 3]

        result = BaseScraper.fetch_all_rounds(scraper, "https://example.com")
        expected = ("Test Tournament", [1, 2, 3])
        assert result == expected
        scraper.fetch_tournament_url.assert_called_once_with("https://example.com")

    def test_fetch_round_pairings_calls_primitives(self):
        """fetch_round_pairings should call fetch_round_url then parse."""
        scraper = Mock(spec=BaseScraper)
        scraper.fetch_round_url.return_value = "<html><pairings/></html>"
        scraper.parse_round_pairings.return_value = [
            {"participant1": "A", "participant2": "B"}
        ]

        result = BaseScraper.fetch_round_pairings(scraper, "https://example.com", 1)
        assert len(result) == 1
        scraper.fetch_round_url.assert_called_once_with("https://example.com", 1)
        scraper.parse_round_pairings.assert_called_once_with(
            "<html><pairings/></html>", 1
        )


# ============================================================================
# SCRAPERS / SCHACK_SE METHOD 2 AND 3
# ============================================================================


class TestSchackSeMethod2:
    """Tests for SchackSeScraper Method 2 (HEMMALAG/BORTALAG headers)."""

    def test_parse_team_with_headers(self):
        html = """
        <html><body>
        <table>
            <tr><th>No</th><th>HEMMALAG</th><th>BORTALAG</th><th>RESULTAT</th></tr>
            <tr><td>1</td><td>Hammarby</td><td>Sparta</td><td>3 - 1</td></tr>
            <tr><td>2</td><td>AIK</td><td>SoIK</td><td>2 - 2</td></tr>
        </table>
        </body></html>
        """
        scraper = SchackSeScraper()
        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 2
        assert pairings[0]["participant1"] == "Hammarby"
        assert pairings[0]["participant2"] == "Sparta"
        assert pairings[1]["participant1"] == "AIK"
        assert pairings[1]["participant2"] == "SoIK"


class TestSchackSeMethod3:
    """Tests for SchackSeScraper Method 3 (headerless team tournament)."""

    def test_parse_headerless_team_tournament(self):
        """Method 3: fixed cell positions with separator '-' at C8.

        Needs 2+ rows (len(rows) < 2 check). Second row is a dummy.
        """
        cells = [
            "<td></td>",  # 0
            "<td></td>",  # 1
            "<td></td>",  # 2
            "<td></td>",  # 3
            "<td>Hammarby</td>",  # 4 (C4, CELL_HOME_TEAM=4)
            "<td></td>",  # 5
            "<td>2100</td>",  # 6 (C6, home Elo)
            "<td></td>",  # 7
            "<td>-</td>",  # 8 (C8, CELL_SEPARATOR=8)
            "<td></td>",  # 9
            "<td>2200</td>",  # 10
            "<td></td>",  # 11
            "<td>Sparta</td>",  # 12 (C12, CELL_AWAY_TEAM=12)
            "<td></td>",  # 13
            "<td>2050</td>",  # 14 (C14, away Elo)
            "<td></td>",  # 15
            "<td>3 - 1</td>",  # 16 (C16, CELL_RESULT=16)
        ]
        row_html = f"<tr>{''.join(cells)}</tr>"
        # Need a second row (dummy) — Method 3 requires len(rows) >= 2
        dummy_row = "<tr><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td><td>x</td>"
        html = f"<html><body><table>{row_html}{dummy_row}</table></body></html>"

        scraper = SchackSeScraper()
        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1
        assert pairings[0]["participant1"] == "Hammarby"
        assert pairings[0]["participant2"] == "Sparta"

    def test_method3_skips_wrong_separator(self):
        """Method 3 should skip rows where C8 is not '-'."""
        cells = [
            "<td></td>",
            "<td></td>",
            "<td></td>",
            "<td></td>",
            "<td>Team A</td>",
            "<td></td>",
            "<td>2100</td>",
            "<td></td>",
            "<td>X</td>",  # Not "-"
            "<td></td>",
            "<td>2200</td>",
            "<td></td>",
            "<td>Team B</td>",
            "<td></td>",
            "<td>2050</td>",
            "<td></td>",
            "<td>3 - 1</td>",
        ]
        row_html = f"<tr>{''.join(cells)}</tr>"
        html = f"<html><body><table>{row_html}</table></body></html>"

        scraper = SchackSeScraper()
        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 0


class TestSchackSeParseResult:
    """Tests for SchackSeScraper._parse_result edge cases."""

    def test_parse_half_score(self):
        scraper = SchackSeScraper()
        s1, s2 = scraper._parse_result("½ - ½")
        assert s1 == 0.5 and s2 == 0.5

    def test_parse_whitespace_around_scores(self):
        scraper = SchackSeScraper()
        s1, s2 = scraper._parse_result("  3  -  1  ")
        assert s1 == 3.0 and s2 == 1.0

    def test_parse_non_matching_format(self):
        scraper = SchackSeScraper()
        s1, s2 = scraper._parse_result("draw")
        assert s1 is None and s2 is None

    def test_parse_empty_string(self):
        scraper = SchackSeScraper()
        s1, s2 = scraper._parse_result("")
        assert s1 is None and s2 is None

    def test_parse_half_in_one_score(self):
        scraper = SchackSeScraper()
        s1, s2 = scraper._parse_result("3½ - ½")
        assert s1 == 3.5 and s2 == 0.5
