"""Scraper presenter - handles tournament scraping and import logic."""

from collections.abc import Callable

from PyQt6.QtWidgets import QMessageBox
from sqlalchemy.orm import Session

from database.queries import get_round, get_tournament
from logic.pairing import PairingData, RoundData
from logic.tournament import import_rounds_from_data
from scrapers import SchackSeScraper
from scrapers.base import BaseScraper


class ScraperPresenter:
    """Handles tournament scraping and import logic.

    Separates scraping orchestration from GUI concerns.
    """

    def __init__(
        self,
        session: Session,
        tournament_id: int,
        on_rounds_fetched: Callable[[int], None],
    ):
        self.session = session
        self.tournament_id = tournament_id
        self.on_rounds_fetched = on_rounds_fetched

    def determine_rounds_to_fetch(self, available_rounds: list[int]) -> list[int]:
        """Return rounds that don't exist in the database yet.

        If all rounds exist, asks user for overwrite confirmation.
        """
        rounds_to_fetch = []
        for r in available_rounds:
            if get_round(self.session, self.tournament_id, r) is None:
                rounds_to_fetch.append(r)

        if not rounds_to_fetch:
            if not self._confirm_overwrite():
                return []
            rounds_to_fetch = available_rounds

        return rounds_to_fetch

    def _confirm_overwrite(self) -> bool:
        """Ask user if they want to overwrite existing rounds."""
        reply = QMessageBox.question(
            None,
            "Confirm",
            "All rounds already exist. Re-fetch and overwrite?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def create_pairing_data(self, scraper_pairings: list[dict]) -> list[PairingData]:
        """Transform scraper output into PairingData objects."""
        return [
            PairingData(
                participant1_name=p["participant1"],
                participant2_name=p["participant2"],
                board_number=p.get("board_number"),
                score1=p.get("score1"),
                score2=p.get("score2"),
            )
            for p in scraper_pairings
        ]

    def import_single_round(
        self,
        scraper: BaseScraper,
        url: str,
        round_num: int,
        tournament_type: str,
    ) -> None:
        """Import a single round from scraper data."""
        pairings_data = scraper.fetch_round_pairings(url, round_num)
        pairings = self.create_pairing_data(pairings_data)
        round_data = RoundData(round_number=round_num, pairings=pairings)
        import_rounds_from_data(
            self.session, self.tournament_id, [round_data], tournament_type
        )

    def fetch_and_import(self, url: str) -> int:
        """Execute full scrape + import flow.

        Tries API scraper first (more reliable for individual tournaments),
        falls back to HTML scraper if API fails.

        Returns the number of rounds imported (0 if cancelled or failed).
        """
        from scrapers import SchackSeApiScraper

        scraper: BaseScraper | None = None

        # Try API scraper first
        try:
            scraper = SchackSeApiScraper()
            name, rounds = scraper.fetch_all_rounds(url)
            if not rounds:
                raise ValueError("API returned no rounds")
        except Exception:
            # Fall back to HTML scraper
            scraper = SchackSeScraper()
            name, rounds = scraper.fetch_all_rounds(url)

        if not rounds:
            return -1  # Signal: no rounds found

        rounds_to_fetch = self.determine_rounds_to_fetch(rounds)
        if not rounds_to_fetch:
            return 0  # Cancelled by user

        tournament = get_tournament(self.session, self.tournament_id)
        tournament_type = tournament.tournament_type if tournament else "individual"

        for round_num in rounds_to_fetch:
            self.import_single_round(scraper, url, round_num, tournament_type)

        self.on_rounds_fetched(len(rounds_to_fetch))
        return len(rounds_to_fetch)
