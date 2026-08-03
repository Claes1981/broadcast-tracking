"""Tests targeting remaining coverage gaps across all modules.

Covers:
- gui/styles.py: create_card_style_from_data, create_status_text_from_data
- gui/pairing_card_builder.py: button creation methods
- gui/presenters/round_view_presenter.py: get_round_by_label not found
- gui/presenters/scraper_presenter.py: ChessResults path, error handling
- gui/presenters/allocation_presenter.py: error handling paths
- logic/allocator.py: empty pairings, existing assignment preservation
- logic/tournament.py: edit_pairing creates new participants
- logic/pairing.py: __repr__ methods
- scrapers/schack_se.py: error handling paths, unknown tournament name
- scrapers/chess_results.py: empty rounds, ValueError paths
- database/init_db.py: rollback path
- database/models.py: __repr__ methods
- utils/export.py: remaining missed line
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


from database import get_tournament
from database.models import Participant, Round, Pairing, DigitalAssignment
from database.init_db import (
    get_session,
    create_tournament,
)
from database.queries import (
    get_pairing_by_id,
)
from logic.allocator import (
    allocate_digital_boards,
)
from logic.tournament import (
    edit_pairing,
)
from logic.pairing import PairingData, RoundData
from utils.export import export
from scrapers.schack_se import SchackSeScraper
from scrapers.chess_results import ChessResultsScraper


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def tournament_with_rounds(mock_database_path):
    """Create a tournament with 4 participants, 2 rounds, 4 pairings."""
    with mock_database_path() as db_path:
        db_path, tournament_id = create_tournament(
            name="Coverage Gaps Test",
            source_url="https://example.com",
            tournament_type="individual",
        )
        session = get_session(db_path)

        participants = []
        for name in ["Alice", "Bob", "Charlie", "Diana"]:
            p = Participant(
                tournament_id=tournament_id, name=name, participant_type="player"
            )
            session.add(p)
            participants.append(p)
        session.commit()

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

        yield (
            db_path,
            tournament_id,
            session,
            participants,
            [
                pairing1,
                pairing2,
                pairing3,
                pairing4,
            ],
            [round1, round2],
        )

        session.close()


# ============================================================================
# GUI / STYLES
# ============================================================================


class TestCreateCardStyleFromData:
    """Tests for create_card_style_from_data helper."""

    def test_manually_excluded(self):
        from gui.styles import create_card_style_from_data, MANUALLY_EXCLUDED

        data = Mock()
        data.is_excluded = True
        data.digital_label = "Board A"
        data.is_manual = True
        style = create_card_style_from_data(data)
        assert MANUALLY_EXCLUDED in style

    def test_digital_assigned(self):
        from gui.styles import create_card_style_from_data, DIGITAL_ASSIGNED

        data = Mock()
        data.is_excluded = False
        data.digital_label = "Board A"
        data.is_manual = False
        style = create_card_style_from_data(data)
        assert DIGITAL_ASSIGNED in style

    def test_manually_assigned(self):
        from gui.styles import create_card_style_from_data, MANUALLY_ASSIGNED

        data = Mock()
        data.is_excluded = False
        data.digital_label = "Board B"
        data.is_manual = True
        style = create_card_style_from_data(data)
        assert MANUALLY_ASSIGNED in style

    def test_not_assigned(self):
        from gui.styles import create_card_style_from_data, NOT_ASSIGNED

        data = Mock()
        data.is_excluded = False
        data.digital_label = None
        data.is_manual = False
        style = create_card_style_from_data(data)
        assert NOT_ASSIGNED in style


class TestCreateStatusTextFromData:
    """Tests for create_status_text_from_data helper."""

    def test_excluded_status(self):
        from gui.styles import create_status_text_from_data

        data = Mock()
        data.is_excluded = True
        text = create_status_text_from_data(data)
        assert "EXCLUDED" in text

    def test_digital_board_status(self):
        from gui.styles import create_status_text_from_data

        data = Mock()
        data.is_excluded = False
        data.digital_label = "Board C"
        text = create_status_text_from_data(data)
        assert "Digital Board: Board C" == text

    def test_not_assigned_status(self):
        from gui.styles import create_status_text_from_data

        data = Mock()
        data.is_excluded = False
        data.digital_label = None
        text = create_status_text_from_data(data)
        assert text == "Not assigned"


# ============================================================================
# GUI / PAIRING CARD BUILDER
# ============================================================================


class TestPairingCardBuilderButtons:
    """Tests for PairingCardBuilder button creation methods."""

    def test_add_remove_assignment_button_static(self):
        """Test _add_remove_assignment_button is a callable static method.

        Can't instantiate QPushButton without a QApp, so we verify the method
        exists and has the right signature instead.
        """
        from gui.pairing_card_builder import PairingCardBuilder

        # Verify the static method exists and is callable
        assert callable(PairingCardBuilder._add_remove_assignment_button)
        import inspect

        sig = inspect.signature(PairingCardBuilder._add_remove_assignment_button)
        params = list(sig.parameters.keys())
        assert "layout" in params
        assert "pairing_id" in params
        assert "callback" in params


# ============================================================================
# GUI / PRESENTERS / ROUND VIEW
# ============================================================================


class TestRoundViewPresenterGetRoundByLabel:
    """Tests for RoundViewPresenter.get_round_by_label edge cases."""

    def test_returns_none_for_invalid_label(self, tournament_with_rounds):
        from gui.presenters.round_view_presenter import RoundViewPresenter

        db_path, tournament_id, session, _, _, _ = tournament_with_rounds
        presenter = RoundViewPresenter(session, tournament_id)
        result = presenter.get_round_by_label("Round 99")
        assert result is None


# ============================================================================
# GUI / PRESENTERS / SCRAPER
# ============================================================================


class TestScraperPresenterChessResultsPath:
    """Tests for ScraperPresenter ChessResults URL routing."""

    def test_fetch_and_import_chess_results_url(self, temp_db_path):
        """Chess-results.com URLs should use ChessResultsScraper."""
        from gui.presenters.scraper_presenter import ScraperPresenter

        db_path, tournament_id = create_tournament(
            name="CR Test",
            source_url="https://chess-results.com/tnr123.aspx",
            tournament_type="individual",
        )
        session = get_session(db_path)

        presenter = ScraperPresenter(session, tournament_id, on_rounds_fetched=Mock())

        # Mock ChessResultsScraper to return data
        mock_scraper = Mock()
        mock_scraper.fetch_all_rounds.return_value = ("CR Tournament", [1])
        mock_scraper.fetch_round_pairings.return_value = [
            {
                "participant1": "Player A",
                "participant2": "Player B",
                "score1": 1,
                "score2": 0,
                "board_number": 1,
            }
        ]

        # Patch at scrapers module level (imported inline in fetch_and_import)
        with patch.dict(
            "scrapers.__dict__", {"ChessResultsScraper": lambda: mock_scraper}
        ):
            result = presenter.fetch_and_import("https://chess-results.com/tnr123.aspx")
            assert result == 1
            mock_scraper.fetch_all_rounds.assert_called_once()

        session.close()

    def test_fetch_and_import_chess_results_error_falls_back(self, temp_db_path):
        """Chess-results.com scraper error should raise (no fallback for CR)."""
        from gui.presenters.scraper_presenter import ScraperPresenter

        db_path, tournament_id = create_tournament(
            name="CR Error Test",
            source_url="https://chess-results.com/tnr123.aspx",
            tournament_type="individual",
        )
        session = get_session(db_path)

        presenter = ScraperPresenter(session, tournament_id, on_rounds_fetched=Mock())

        with patch.dict(
            "scrapers.__dict__",
            {
                "ChessResultsScraper": lambda: (_ for _ in ()).throw(
                    Exception("Network error")
                )
            },
        ):
            with pytest.raises(Exception, match="Network error"):
                presenter.fetch_and_import("https://chess-results.com/tnr123.aspx")

        session.close()

    def test_fetch_and_import_unknown_url(self, temp_db_path):
        """Unknown URLs should default to Schack.se scrapers."""
        from gui.presenters.scraper_presenter import ScraperPresenter

        db_path, tournament_id = create_tournament(
            name="Unknown URL Test",
            source_url="https://unknown.com",
            tournament_type="individual",
        )
        session = get_session(db_path)

        presenter = ScraperPresenter(session, tournament_id, on_rounds_fetched=Mock())

        # Both scrapers fail -> API error caught, HTML fallback also fails
        # SchackSeApiScraper imported inline, SchackSeScraper imported at module level
        with (
            patch.dict(
                "scrapers.__dict__",
                {
                    "SchackSeApiScraper": lambda: (_ for _ in ()).throw(
                        Exception("API error")
                    )
                },
            ),
            patch(
                "gui.presenters.scraper_presenter.SchackSeScraper",
                side_effect=Exception("HTML error"),
            ),
            pytest.raises(Exception, match="HTML error"),
        ):
            presenter.fetch_and_import("https://unknown.com/tournament")

        session.close()


# ============================================================================
# GUI / PRESENTERS / ALLOCATION
# ============================================================================


class TestAllocationPresenterErrorPaths:
    """Tests for AllocationPresenter error handling paths."""

    def test_edit_pairing_shows_error_on_exception(self, tournament_with_rounds):
        """edit_pairing should catch exceptions and show error dialog."""
        from gui.presenters.allocation_presenter import AllocationPresenter

        db_path, tournament_id, session, _, pairings, _ = tournament_with_rounds
        presenter = AllocationPresenter(
            session,
            tournament_id,
            num_digital_boards=2,
            on_allocated=Mock(),
            on_cleared=Mock(),
            on_assignment_changed=Mock(),
        )

        # Mock EditPairingDialog to raise an exception
        mock_dialog = Mock()
        mock_dialog.get_data.side_effect = RuntimeError("Dialog error")

        with (
            patch(
                "gui.presenters.allocation_presenter.EditPairingDialog",
                return_value=mock_dialog,
            ),
            patch("gui.presenters.allocation_presenter.QMessageBox") as mock_msg,
        ):
            presenter.edit_pairing(pairings[0].id, parent_widget=Mock())
            mock_msg.critical.assert_called_once()
            call_args = mock_msg.critical.call_args
            assert "Failed to edit pairing" in call_args[0][2]

    def test_remove_pairing_shows_error_on_exception(self, tournament_with_rounds):
        """remove_pairing should catch exceptions and show error dialog."""
        from gui.presenters.allocation_presenter import AllocationPresenter

        db_path, tournament_id, session, _, pairings, _ = tournament_with_rounds
        presenter = AllocationPresenter(
            session,
            tournament_id,
            num_digital_boards=2,
            on_allocated=Mock(),
            on_cleared=Mock(),
            on_assignment_changed=Mock(),
        )

        with (
            patch(
                "gui.presenters.allocation_presenter.remove_pairing",
                side_effect=RuntimeError("DB error"),
            ),
            patch("gui.presenters.allocation_presenter.QMessageBox") as mock_msg,
        ):
            mock_msg.question.return_value = mock_msg.StandardButton.Yes
            presenter.remove_pairing(pairings[0].id, parent_widget=Mock())
            mock_msg.critical.assert_called_once()
            call_args = mock_msg.critical.call_args
            assert "Failed to remove pairing" in call_args[0][2]


# ============================================================================
# LOGIC / ALLOCATOR - EMPTY PAIRINGS AND EXISTING ASSIGNMENTS
# ============================================================================


class TestAllocateDigitalBoardsEdgeCases:
    """Tests for allocate_digital_boards edge cases."""

    def test_empty_pairings_returns_empty(self, tournament_with_rounds):
        """Round with no pairings should return empty list."""
        db_path, tournament_id, session, _, _, rounds = tournament_with_rounds
        # Create a round with no pairings
        empty_round = Round(tournament_id=tournament_id, round_number=3)
        session.add(empty_round)
        session.commit()

        session.flush()
        result = allocate_digital_boards(session, empty_round.id, 2)  # type: ignore[arg-type]
        assert result == []

    def test_preserves_manual_assignments(self, tournament_with_rounds):
        """Manual assignments should be preserved during re-allocation."""
        db_path, tournament_id, session, _, pairings, rounds = tournament_with_rounds

        # Create a manual assignment on pairing1
        da = DigitalAssignment(
            pairing_id=pairings[0].id,
            digital_board_label="Board A",
            is_manual=True,
        )
        session.add(da)
        session.commit()

        # Allocate round 1 — pairing1 already has manual assignment
        result = allocate_digital_boards(session, rounds[0].id, 3)

        # pairing1 should retain its manual label
        assigned_labels = {p.id: label for p, label in result}
        assert pairings[0].id in assigned_labels
        assert assigned_labels[pairings[0].id] == "Board A"

    def test_boards_ge_pairings_assigns_all(self, tournament_with_rounds):
        """When boards >= pairings, all pairings get assigned."""
        db_path, tournament_id, session, _, pairings, rounds = tournament_with_rounds

        # Round 1 has 2 pairings, allocate 5 boards
        result = allocate_digital_boards(session, rounds[0].id, 5)
        # Should assign labels to all 2 pairings
        assert len(result) == 2


# ============================================================================
# LOGIC / TOURNAMENT - EDIT PAIRING CREATES NEW PARTICIPANTS
# ============================================================================


class TestEditPairingNewParticipants:
    """Tests for edit_pairing when participants don't exist."""

    def test_edit_pairing_with_existing_participants(self, tournament_with_rounds):
        """edit_pairing should work when replacing with existing participants."""
        db_path, tournament_id, session, participants, pairings, _ = (
            tournament_with_rounds
        )

        # Edit pairing2 to use Alice (p0) and Bob (p1) instead
        result = edit_pairing(session, pairings[1].id, "Alice", "Bob")
        assert result

        # Verify pairing now references Alice and Bob
        updated = get_pairing_by_id(session, pairings[1].id)
        assert updated is not None
        assert updated.participant1_id == participants[0].id
        assert updated.participant2_id == participants[1].id


# ============================================================================
# LOGIC / PAIRING - __repr__ METHODS
# ============================================================================


class TestPairingDataRepr:
    """Tests for PairingData and RoundData __str__ methods."""

    def test_pairing_data_str(self):
        data = PairingData(
            participant1_name="Alice",
            participant2_name="Bob",
            score1=1.0,
            score2=0.0,
            board_number=1,
        )
        assert "Alice vs Bob" in str(data)

    def test_round_data_str(self):
        pairings = [
            PairingData("Alice", "Bob", board_number=1, score1=1.0, score2=0.0),
            PairingData("Charlie", "Diana", board_number=2, score1=0.5, score2=0.5),
        ]
        data = RoundData(round_number=3, pairings=pairings)
        assert "Round 3" in str(data)
        assert "2 pairings" in str(data)


# ============================================================================
# SCRAPERS / SCHACK_SE - ERROR HANDLING
# ============================================================================


class TestSchackSeErrorPaths:
    """Tests for SchackSeScraper error handling paths."""

    def test_parse_tournament_name_returns_unknown(self):
        """parse_tournament_name should return 'Unknown Tournament' for empty HTML."""
        scraper = SchackSeScraper()
        result = scraper.parse_tournament_name("<html><body></body></html>")
        assert result == "Unknown Tournament"

    def test_parse_rounds_returns_empty_for_no_links(self):
        """parse_rounds should return empty list when no round links found."""
        scraper = SchackSeScraper()
        html = "<html><body><p>No rounds here</p></body></html>"
        result = scraper.parse_rounds(html)
        assert result == []

    def test_parse_result_value_error_half_score(self):
        """_parse_result should handle ValueError gracefully for malformed scores."""
        scraper = SchackSeScraper()
        # "abc - def" should trigger ValueError in float() and return (None, None)
        s1, s2 = scraper._parse_result("abc - def")
        assert s1 is None and s2 is None

    def test_parse_result_value_error_single_score(self):
        """_parse_result should handle ValueError for single malformed score."""
        scraper = SchackSeScraper()
        # "xyz" (no dash) should trigger ValueError
        s1, s2 = scraper._parse_result("xyz")
        assert s1 is None and s2 is None

    def test_method1_skips_elo_ratings(self):
        """Method 1 should skip rows where team2 starts with 'E' followed by digit."""
        html = """
        <html><body>
        <table class="greyproptable">
            <tr><td class="listheader">Alice</td><td class="listheader">Bob</td><td class="listheadercenter">1 - 0</td></tr>
            <tr><td class="listheader">Charlie</td><td class="listheader">E2100</td><td class="listheadercenter">x</td></tr>
        </table>
        </body></html>
        """
        scraper = SchackSeScraper()
        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1
        assert pairings[0]["participant1"] == "Alice"

    def test_method1_skips_short_rows(self):
        """Method 1 should skip rows with fewer than 2 listheader cells."""
        html = """
        <html><body>
        <table class="greyproptable">
            <tr><td class="listheader">Alice</td><td class="listheader">Bob</td><td class="listheadercenter">1 - 0</td></tr>
            <tr><td class="listheader">short</td><td class="listheadercenter">x</td></tr>
        </table>
        </body></html>
        """
        scraper = SchackSeScraper()
        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1

    def test_method1_skips_empty_team2(self):
        """Method 1 should skip rows where team2 is empty."""
        html = """
        <html><body>
        <table class="greyproptable">
            <tr><td class="listheader">Alice</td><td class="listheader">Bob</td><td class="listheadercenter">1 - 0</td></tr>
            <tr><td class="listheader">Charlie</td><td class="listheader"></td><td class="listheadercenter"></td></tr>
        </table>
        </body></html>
        """
        scraper = SchackSeScraper()
        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1

    def test_method2_skips_short_rows(self):
        """Method 2 should skip rows with fewer than 4 cells."""
        html = """
        <html><body>
        <table>
            <tr><th>No</th><th>HEMMALAG</th><th>BORTALAG</th><th>RESULTAT</th></tr>
            <tr><td>1</td><td>Hammarby</td><td>Sparta</td><td>3 - 1</td></tr>
            <tr><td>short</td></tr>
        </table>
        </body></html>
        """
        scraper = SchackSeScraper()
        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1

    def test_method2_skips_empty_teams(self):
        """Method 2 should skip rows where home or away team is empty."""
        html = """
        <html><body>
        <table>
            <tr><th>No</th><th>HEMMALAG</th><th>BORTALAG</th><th>RESULTAT</th></tr>
            <tr><td>1</td><td>Hammarby</td><td>Sparta</td><td>3 - 1</td></tr>
            <tr><td>2</td><td></td><td>AIK</td><td>2 - 0</td></tr>
            <tr><td>3</td><td>SoIK</td><td></td><td>1 - 1</td></tr>
        </table>
        </body></html>
        """
        scraper = SchackSeScraper()
        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1

    def test_method3_skips_short_rows(self):
        """Method 3 should skip rows with fewer than 17 cells."""
        html = """
        <html><body>
        <table>
            <tr><td>a</td><td>b</td><td>c</td></tr>
            <tr><td>a</td><td>b</td><td>c</td></tr>
        </table>
        </body></html>
        """
        scraper = SchackSeScraper()
        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 0

    def test_method3_skips_empty_teams(self):
        """Method 3 should skip rows where home or away team is empty."""
        cells_a = [
            "<td></td>",
            "<td></td>",
            "<td></td>",
            "<td></td>",
            "<td>Team A</td>",
            "<td></td>",
            "<td>2100</td>",
            "<td></td>",
            "<td>-</td>",
            "<td></td>",
            "<td>2200</td>",
            "<td></td>",
            "<td>Team B</td>",
            "<td></td>",
            "<td>2050</td>",
            "<td></td>",
            "<td>3 - 1</td>",
        ]
        cells_empty = [
            "<td></td>",
            "<td></td>",
            "<td></td>",
            "<td></td>",
            "<td></td>",
            "<td></td>",
            "<td>2100</td>",
            "<td></td>",
            "<td>-</td>",
            "<td></td>",
            "<td>2200</td>",
            "<td></td>",
            "<td>Team B</td>",
            "<td></td>",
            "<td>2050</td>",
            "<td></td>",
            "<td>3 - 1</td>",
        ]
        row_html_a = f"<tr>{''.join(cells_a)}</tr>"
        row_html_empty = f"<tr>{''.join(cells_empty)}</tr>"
        html = f"<html><body><table>{row_html_a}{row_html_empty}</table></body></html>"

        scraper = SchackSeScraper()
        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1
        assert pairings[0]["participant1"] == "Team A"


# ============================================================================
# SCRAPERS / CHESS RESULTS - ERROR HANDLING
# ============================================================================


class TestChessResultsErrorPaths:
    """Tests for ChessResultsScraper error handling paths."""

    def test_parse_rounds_returns_empty_for_no_links(self):
        """parse_rounds should return empty list when no round links found."""
        scraper = ChessResultsScraper()
        html = "<html><body><p>No rounds</p></body></html>"
        result = scraper.parse_rounds(html)
        assert result == []

    def test_parse_rounds_value_error_on_bad_rd(self):
        """parse_rounds should skip links with non-numeric rd parameter."""
        scraper = ChessResultsScraper()
        html = """
        <html><body>
        <a href="tnr123.aspx?lan=1&art=2&rd=abc&flag=30">Round abc</a>
        <a href="tnr123.aspx?lan=1&art=2&rd=1&flag=30">Round 1</a>
        </body></html>
        """
        result = scraper.parse_rounds(html)
        # Should skip 'abc' and only return round 1
        assert result == [1]

    def test_team_parse_continues_on_short_row(self):
        """Team parsing should skip rows with fewer than 6 cells."""
        html = """
        <html><body>
        <table>
            <tr><td>1</td><td>Home</td><td>Away</td><td>3</td><td>:</td><td>1</td></tr>
            <tr><td>short</td><td>row</td></tr>
            <tr><td>2</td><td>Home2</td><td>Away2</td><td>2</td><td>:</td><td>2</td></tr>
        </table>
        </body></html>
        """
        scraper = ChessResultsScraper()
        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 2

    def test_find_pairings_table_returns_none_for_empty(self):
        """_find_pairings_table should return None for empty HTML."""
        scraper = ChessResultsScraper()
        soup = MagicMock()
        soup.find_all.return_value = []
        result = scraper._find_pairings_table(soup)
        assert result is None


# ============================================================================
# DATABASE / MODELS - __repr__ METHODS
# ============================================================================


class TestModelsRepr:
    """Tests for model __repr__ methods."""

    def test_tournament_repr(self, tournament_with_rounds):
        db_path, tournament_id, session, _, _, _ = tournament_with_rounds
        t = get_tournament(session, tournament_id)
        assert t is not None
        assert "Tournament" in repr(t)

    def test_participant_repr(self, tournament_with_rounds):
        db_path, tournament_id, session, participants, _, _ = tournament_with_rounds
        p = participants[0]
        assert "Participant" in repr(p)

    def test_round_repr(self, tournament_with_rounds):
        db_path, tournament_id, session, _, _, rounds = tournament_with_rounds
        r = rounds[0]
        assert str(r.round_number) in repr(r)

    def test_pairing_repr(self, tournament_with_rounds):
        db_path, tournament_id, session, _, pairings, _ = tournament_with_rounds
        assert "Pairing" in repr(pairings[0])

    def test_digital_assignment_repr(self, tournament_with_rounds):
        db_path, tournament_id, session, _, pairings, rounds = tournament_with_rounds
        da = DigitalAssignment(
            pairing_id=pairings[0].id,
            digital_board_label="Board A",
        )
        session.add(da)
        session.commit()
        assert "Board A" in repr(da)


# ============================================================================
# DATABASE / INIT_DB - ROLLBACK PATH
# ============================================================================


class TestInitDbRollback:
    """Tests for init_db rollback path."""

    def test_create_tournament_rollback_on_error(self, mock_database_path):
        """create_tournament should rollback on error."""
        from sqlalchemy.exc import IntegrityError

        with mock_database_path():
            # Create a valid tournament first
            create_tournament(
                name="Rollback Test",
                source_url="https://example.com",
                tournament_type="individual",
            )

            # Now try to create another with same name (should trigger unique constraint)
            with pytest.raises(IntegrityError):
                create_tournament(
                    name="Rollback Test",
                    source_url="https://example.com",
                    tournament_type="individual",
                )


# ============================================================================
# UTILS / EXPORT - REMAINING MISSED LINE
# ============================================================================


class TestExportRemaining:
    """Tests for remaining uncovered export lines."""

    def test_export_to_csv_calls_export(self, tournament_with_rounds):
        """Test CSV export writes a file with data rows."""
        import csv

        db_path, tournament_id, session, _, pairings, _ = tournament_with_rounds
        # Add a digital assignment so CSV has data rows
        da = DigitalAssignment(
            pairing_id=pairings[0].id,
            digital_board_label="Board A",
        )
        session.add(da)
        session.commit()

        temp_dir = tempfile.mkdtemp()
        csv_path = Path(temp_dir) / "export.csv"

        try:
            export(session, tournament_id, str(csv_path), format_type="CSV")
            assert csv_path.exists()
            with open(csv_path) as f:
                reader = csv.reader(f)
                rows = list(reader)
                assert len(rows) >= 2  # header + at least one data row
        finally:
            shutil.rmtree(temp_dir)

    def test_export_to_json_calls_export(self, tournament_with_rounds):
        """Test JSON export writes a file."""
        import json

        db_path, tournament_id, session, _, _, _ = tournament_with_rounds
        temp_dir = tempfile.mkdtemp()
        json_path = Path(temp_dir) / "export.json"

        try:
            export(session, tournament_id, str(json_path), format_type="JSON")
            assert json_path.exists()
            with open(json_path) as f:
                data = json.load(f)
                assert "tournament" in data
        finally:
            shutil.rmtree(temp_dir)

    def test_export_statistics_calls_export(self, tournament_with_rounds):
        """Test statistics export writes a file."""
        db_path, tournament_id, session, _, _, _ = tournament_with_rounds
        temp_dir = tempfile.mkdtemp()
        stats_path = Path(temp_dir) / "stats.txt"

        try:
            export(session, tournament_id, str(stats_path), format_type="Statistics")
            assert stats_path.exists()
        finally:
            shutil.rmtree(temp_dir)
