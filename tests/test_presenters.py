"""Tests for presenters (Allocation, Scraper, ManualEntry).

Mocks GUI interactions (QMessageBox, QInputDialog) and uses real DB data.
"""

from unittest.mock import Mock, patch

from logic.pairing import PairingData, RoundData
from logic.tournament import import_rounds_from_data

from gui.presenters.allocation_presenter import AllocationPresenter
from gui.presenters.scraper_presenter import ScraperPresenter
from gui.presenters.manual_entry_presenter import ManualEntryPresenter


# ============================================================================
# ALLOCATION PRESENTER TESTS
# ============================================================================


class TestAllocationPresenterAllocate:
    """Tests for AllocationPresenter.allocate_round()."""

    def test_allocate_round_success(self, tournament_with_rounds):
        """Test successful allocation calls callbacks."""
        session, tournament_id, _ = tournament_with_rounds
        on_allocated = Mock()
        on_changed = Mock()

        presenter = AllocationPresenter(
            session, tournament_id, 2, on_allocated, Mock(), on_changed
        )

        from database.queries import get_round

        round_obj = get_round(session, tournament_id, 1)
        assert round_obj is not None

        with patch("gui.presenters.allocation_presenter.QMessageBox"):
            presenter.allocate_round(int(round_obj.id), Mock())

        on_allocated.assert_called_once()
        on_changed.assert_called_once()

    def test_allocate_round_error_shows_critical(self, tournament_with_rounds):
        """Test that allocation errors show critical message."""
        session, tournament_id, _ = tournament_with_rounds

        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), Mock()
        )

        from database.queries import get_round

        round_obj = get_round(session, tournament_id, 1)
        assert round_obj is not None

        with patch(
            "gui.presenters.allocation_presenter.allocate_digital_boards",
            side_effect=Exception("DB error"),
        ):
            with patch("gui.presenters.allocation_presenter.QMessageBox") as mock_msg:
                presenter.allocate_round(int(round_obj.id), Mock())
                mock_msg.critical.assert_called_once()


class TestAllocationPresenterClear:
    """Tests for AllocationPresenter.clear_round()."""

    def test_clear_round_confirmed(self, tournament_with_rounds):
        """Test clearing round when user confirms."""
        session, tournament_id, _ = tournament_with_rounds
        on_cleared = Mock()
        on_changed = Mock()

        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), on_cleared, on_changed
        )

        from database.queries import get_round

        round_obj = get_round(session, tournament_id, 1)
        assert round_obj is not None

        with patch("gui.presenters.allocation_presenter.QMessageBox") as mock_msg:
            mock_msg.question.return_value = mock_msg.StandardButton.Yes
            presenter.clear_round(int(round_obj.id), Mock())

        on_changed.assert_called_once()

    def test_clear_round_cancelled(self, tournament_with_rounds):
        """Test that clear returns 0 when user cancels."""
        session, tournament_id, _ = tournament_with_rounds
        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), Mock()
        )

        from database.queries import get_round

        round_obj = get_round(session, tournament_id, 1)
        assert round_obj is not None

        with patch("gui.presenters.allocation_presenter.QMessageBox") as mock_msg:
            mock_msg.question.return_value = mock_msg.StandardButton.No
            count = presenter.clear_round(int(round_obj.id), Mock())

        assert count == 0

    def test_clear_round_error(self, tournament_with_rounds):
        """Test clear_round handles exceptions."""
        session, tournament_id, _ = tournament_with_rounds
        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), Mock()
        )

        from database.queries import get_round

        round_obj = get_round(session, tournament_id, 1)
        assert round_obj is not None

        with patch("gui.presenters.allocation_presenter.QMessageBox") as mock_msg:
            mock_msg.question.return_value = mock_msg.StandardButton.Yes
            with patch(
                "gui.presenters.allocation_presenter.clear_round_assignments",
                side_effect=Exception("fail"),
            ):
                count = presenter.clear_round(int(round_obj.id), Mock())
                mock_msg.critical.assert_called_once()

        assert count == 0


class TestAllocationPresenterManualAssign:
    """Tests for AllocationPresenter.manual_assign()."""

    def test_manual_assign_success(self, tournament_with_rounds):
        """Test successful manual board assignment."""
        session, tournament_id, _ = tournament_with_rounds
        on_changed = Mock()

        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), on_changed
        )

        with patch("gui.presenters.allocation_presenter.QInputDialog") as mock_input:
            mock_input.getItem.return_value = ("Board A", True)
            presenter.manual_assign(1, Mock())

        on_changed.assert_called_once()

    def test_manual_assign_cancelled(self, tournament_with_rounds):
        """Test that manual assign does nothing when cancelled."""
        session, tournament_id, _ = tournament_with_rounds
        on_changed = Mock()

        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), on_changed
        )

        with patch("gui.presenters.allocation_presenter.QInputDialog") as mock_input:
            mock_input.getItem.return_value = ("", False)
            presenter.manual_assign(1, Mock())

        on_changed.assert_not_called()

    def test_manual_assign_error(self, tournament_with_rounds):
        """Test manual assign shows error on failure."""
        session, tournament_id, _ = tournament_with_rounds
        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), Mock()
        )

        with patch("gui.presenters.allocation_presenter.QInputDialog") as mock_input:
            mock_input.getItem.return_value = ("Board A", True)
            with patch(
                "gui.presenters.allocation_presenter.manually_assign_digital_board",
                side_effect=Exception("fail"),
            ):
                with patch(
                    "gui.presenters.allocation_presenter.QMessageBox"
                ) as mock_msg:
                    presenter.manual_assign(1, Mock())
                    mock_msg.critical.assert_called_once()


class TestAllocationPresenterRemoveAssignment:
    """Tests for AllocationPresenter.remove_assignment()."""

    def test_remove_assignment_success(self, tournament_with_rounds):
        """Test successful removal of assignment."""
        session, tournament_id, _ = tournament_with_rounds
        on_changed = Mock()

        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), on_changed
        )

        presenter.remove_assignment(1, Mock())
        on_changed.assert_called_once()

    def test_remove_assignment_error(self, tournament_with_rounds):
        """Test remove_assignment shows error on failure."""
        session, tournament_id, _ = tournament_with_rounds
        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), Mock()
        )

        with patch(
            "gui.presenters.allocation_presenter.manually_assign_digital_board",
            side_effect=Exception("fail"),
        ):
            with patch("gui.presenters.allocation_presenter.QMessageBox") as mock_msg:
                presenter.remove_assignment(1, Mock())
                mock_msg.critical.assert_called_once()


class TestAllocationPresenterToggleExclude:
    """Tests for AllocationPresenter.toggle_exclude()."""

    def test_toggle_exclude_no_assignment(self, tournament_with_rounds):
        """Test toggle when no assignment exists (should set excluded=True)."""
        session, tournament_id, _ = tournament_with_rounds
        on_changed = Mock()

        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), on_changed
        )

        presenter.toggle_exclude(1, Mock())
        on_changed.assert_called_once()

    def test_toggle_exclude_error(self, tournament_with_rounds):
        """Test toggle_exclude shows error on failure."""
        session, tournament_id, _ = tournament_with_rounds
        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), Mock()
        )

        with patch(
            "gui.presenters.allocation_presenter.exclude_from_digital",
            side_effect=Exception("fail"),
        ):
            with patch("gui.presenters.allocation_presenter.QMessageBox") as mock_msg:
                presenter.toggle_exclude(1, Mock())
                mock_msg.critical.assert_called_once()


class TestAllocationPresenterEditPairing:
    """Tests for AllocationPresenter.edit_pairing()."""

    def test_edit_pairing_no_pairing(self, tournament_with_rounds):
        """Test edit_pairing returns early for non-existent pairing."""
        session, tournament_id, _ = tournament_with_rounds
        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), Mock()
        )

        # Should not crash - pairing_id 99999 doesn't exist
        presenter.edit_pairing(999999, Mock())

    def test_edit_pairing_cancelled(self, tournament_with_rounds):
        """Test edit_pairing does nothing when dialog is cancelled."""
        session, tournament_id, _ = tournament_with_rounds
        on_changed = Mock()

        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), on_changed
        )

        from database.queries import get_all_rounds, get_round_pairings

        rounds = get_all_rounds(session, tournament_id)
        pairings = get_round_pairings(session, int(rounds[0].id))
        pairing_id = int(pairings[0].id)

        with patch(
            "gui.presenters.allocation_presenter.EditPairingDialog"
        ) as mock_dialog:
            mock_dialog.return_value.exec.return_value = False
            presenter.edit_pairing(pairing_id, Mock())

        on_changed.assert_not_called()


class TestAllocationPresenterRemovePairing:
    """Tests for AllocationPresenter.remove_pairing()."""

    def test_remove_pairing_confirmed(self, tournament_with_rounds):
        """Test remove_pairing when user confirms."""
        session, tournament_id, _ = tournament_with_rounds
        on_changed = Mock()

        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), on_changed
        )

        from database.queries import get_all_rounds, get_round_pairings

        rounds = get_all_rounds(session, tournament_id)
        pairings = get_round_pairings(session, int(rounds[0].id))
        pairing_id = int(pairings[0].id)

        with patch("gui.presenters.allocation_presenter.QMessageBox") as mock_msg:
            mock_msg.question.return_value = mock_msg.StandardButton.Yes
            presenter.remove_pairing(pairing_id, Mock())
            mock_msg.information.assert_called()

        on_changed.assert_called_once()

    def test_remove_pairing_cancelled(self, tournament_with_rounds):
        """Test remove_pairing does nothing when cancelled."""
        session, tournament_id, _ = tournament_with_rounds
        on_changed = Mock()

        presenter = AllocationPresenter(
            session, tournament_id, 2, Mock(), Mock(), on_changed
        )

        from database.queries import get_all_rounds, get_round_pairings

        rounds = get_all_rounds(session, tournament_id)
        pairings = get_round_pairings(session, int(rounds[0].id))
        pairing_id = int(pairings[0].id)

        with patch("gui.presenters.allocation_presenter.QMessageBox") as mock_msg:
            mock_msg.question.return_value = mock_msg.StandardButton.No
            presenter.remove_pairing(pairing_id, Mock())
            mock_msg.information.assert_not_called()

        on_changed.assert_not_called()


# ============================================================================
# SCRAPER PRESENTER TESTS
# ============================================================================


class TestScraperPresenterDetermineRounds:
    """Tests for ScraperPresenter.determine_rounds_to_fetch()."""

    def test_returns_only_new_rounds(self, tournament_session):
        """Test that only rounds not in DB are returned."""
        session, tournament_id, _ = tournament_session

        # Import round 1
        pairings = [PairingData("A", "B", score1=1, score2=0)]
        import_rounds_from_data(
            session, tournament_id, [RoundData(1, pairings)], "individual"
        )
        session.commit()

        presenter = ScraperPresenter(session, tournament_id, Mock())
        result = presenter.determine_rounds_to_fetch([1, 2, 3])
        assert result == [2, 3]

    def test_returns_all_when_none_exist(self, tournament_session):
        """Test all rounds returned when none exist in DB."""
        session, tournament_id, _ = tournament_session
        presenter = ScraperPresenter(session, tournament_id, Mock())
        result = presenter.determine_rounds_to_fetch([1, 2, 3])
        assert result == [1, 2, 3]

    def test_confirms_overwrite_when_all_exist(self, tournament_session):
        """Test overwrite confirmation when all rounds exist."""
        session, tournament_id, _ = tournament_session

        for rnum in [1, 2]:
            pairings = [PairingData("A", "B", score1=1, score2=0)]
            import_rounds_from_data(
                session, tournament_id, [RoundData(rnum, pairings)], "individual"
            )
        session.commit()

        presenter = ScraperPresenter(session, tournament_id, Mock())

        with patch("gui.presenters.scraper_presenter.QMessageBox") as mock_msg:
            mock_msg.question.return_value = mock_msg.StandardButton.Yes
            result = presenter.determine_rounds_to_fetch([1, 2])

        assert result == [1, 2]

    def test_returns_empty_when_overwrite_cancelled(self, tournament_session):
        """Test empty result when user cancels overwrite."""
        session, tournament_id, _ = tournament_session

        for rnum in [1, 2]:
            pairings = [PairingData("A", "B", score1=1, score2=0)]
            import_rounds_from_data(
                session, tournament_id, [RoundData(rnum, pairings)], "individual"
            )
        session.commit()

        presenter = ScraperPresenter(session, tournament_id, Mock())

        with patch("gui.presenters.scraper_presenter.QMessageBox") as mock_msg:
            mock_msg.question.return_value = mock_msg.StandardButton.No
            result = presenter.determine_rounds_to_fetch([1, 2])

        assert result == []


class TestScraperPresenterCreatePairingData:
    """Tests for ScraperPresenter.create_pairing_data()."""

    def test_transforms_scraper_output(self, tournament_session):
        """Test that scraper dicts are converted to PairingData."""
        session, tournament_id, _ = tournament_session
        presenter = ScraperPresenter(session, tournament_id, Mock())

        scraper_data = [
            {
                "participant1": "Alice",
                "participant2": "Bob",
                "board_number": 1,
                "score1": 1,
                "score2": 0,
            },
        ]

        result = presenter.create_pairing_data(scraper_data)
        assert len(result) == 1
        assert result[0].participant1_name == "Alice"
        assert result[0].participant2_name == "Bob"
        assert result[0].board_number == 1

    def test_handles_missing_optional_fields(self, tournament_session):
        """Test that missing optional fields default to None."""
        session, tournament_id, _ = tournament_session
        presenter = ScraperPresenter(session, tournament_id, Mock())

        scraper_data = [
            {"participant1": "Alice", "participant2": "Bob"},
        ]

        result = presenter.create_pairing_data(scraper_data)
        assert result[0].board_number is None
        assert result[0].score1 is None
        assert result[0].score2 is None


class TestScraperPresenterFetchAndImport:
    """Tests for ScraperPresenter.fetch_and_import()."""

    def test_returns_negative_one_when_no_rounds(self, tournament_session):
        """Test that -1 is returned when no rounds found."""
        session, tournament_id, _ = tournament_session
        presenter = ScraperPresenter(session, tournament_id, Mock())

        with patch("scrapers.SchackSeApiScraper") as mock_api:
            mock_api.return_value.fetch_all_rounds.return_value = ("Tournament", [])
            with patch("scrapers.SchackSeScraper") as mock_html:
                mock_html.return_value.fetch_all_rounds.return_value = (
                    "Tournament",
                    [],
                )
                result = presenter.fetch_and_import("https://example.com?id=1")

        assert result == -1

    def test_returns_zero_when_cancelled(self, tournament_session):
        """Test that 0 is returned when user cancels overwrite."""
        session, tournament_id, _ = tournament_session

        # Pre-import round 1 so overwrite confirmation is triggered
        pairings = [PairingData("A", "B", score1=1, score2=0)]
        import_rounds_from_data(
            session, tournament_id, [RoundData(1, pairings)], "individual"
        )
        session.commit()

        presenter = ScraperPresenter(session, tournament_id, Mock())

        with patch("scrapers.SchackSeApiScraper") as mock_api:
            mock_api.return_value.fetch_all_rounds.return_value = ("Tournament", [1])
            with patch("gui.presenters.scraper_presenter.QMessageBox") as mock_msg:
                mock_msg.question.return_value = mock_msg.StandardButton.No
                result = presenter.fetch_and_import("https://example.com?id=1")

        assert result == 0


# ============================================================================
# MANUAL ENTRY PRESENTER TESTS
# ============================================================================


class TestManualEntryPresenter:
    """Tests for ManualEntryPresenter."""

    def test_get_next_round_number_empty(self, tournament_session):
        """Test next round is 1 when no rounds exist."""
        session, tournament_id, _ = tournament_session
        presenter = ManualEntryPresenter(session, tournament_id, Mock())
        assert presenter.get_next_round_number() == 1

    def test_get_next_round_number_after_rounds(self, tournament_with_rounds):
        """Test next round increments after existing rounds."""
        session, tournament_id, _ = tournament_with_rounds
        presenter = ManualEntryPresenter(session, tournament_id, Mock())
        assert presenter.get_next_round_number() == 2

    def test_get_participant_names(self, tournament_with_rounds):
        """Test participant names are retrieved sorted."""
        session, tournament_id, _ = tournament_with_rounds
        presenter = ManualEntryPresenter(session, tournament_id, Mock())
        names = presenter.get_participant_names()
        assert "Alice" in names
        assert len(names) == 6  # Alice, Bob, Charlie, David, Eve, Frank

    def test_import_manual_round(self, tournament_session):
        """Test importing a manual round."""
        session, tournament_id, _ = tournament_session
        on_added = Mock()

        presenter = ManualEntryPresenter(session, tournament_id, on_added)

        pairings = [
            {"participant1": "Alice", "participant2": "Bob", "score1": 1, "score2": 0},
        ]
        presenter.import_manual_round(1, pairings)

        on_added.assert_called_once_with(1, 1)
