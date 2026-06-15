from abc import ABC, abstractmethod


class BaseScraper(ABC):
    """Abstract base class for tournament scrapers."""

    # -- Low-level primitives (must implement) --

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

    # -- High-level workflow (default implementations, overridable) --

    def fetch_all_rounds(self, url: str) -> tuple[str, list[int]]:
        """Fetch tournament name and all available round numbers."""
        html = self.fetch_tournament_url(url)
        name = self.parse_tournament_name(html)
        rounds = self.parse_rounds(html)
        return name, rounds

    def fetch_round_pairings(self, base_url: str, round_number: int) -> list[dict]:
        """Fetch and parse pairings for a specific round."""
        html = self.fetch_round_url(base_url, round_number)
        return self.parse_round_pairings(html, round_number)
