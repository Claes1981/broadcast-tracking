from abc import ABC, abstractmethod


class BaseScraper(ABC):
    """Abstract base class for tournament scrapers."""

    @abstractmethod
    def fetch_tournament_url(self, url: str) -> str:
        """Fetch the tournament page HTML."""
        pass

    @abstractmethod
    def parse_tournament_name(self, html: str) -> str:
        """Parse the tournament name from HTML."""
        pass

    @abstractmethod
    def parse_rounds(self, html: str) -> list[int]:
        """Parse list of round numbers from HTML."""
        pass

    @abstractmethod
    def fetch_round_url(self, base_url: str, round_number: int) -> str:
        """Fetch a specific round's HTML."""
        pass

    @abstractmethod
    def parse_round_pairings(self, html: str, round_number: int) -> list[dict]:
        """Parse pairings from a round's HTML."""
        pass
