from abc import ABC, abstractmethod
from typing import List, Optional
from bs4 import BeautifulSoup
import requests
import re


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
    def parse_rounds(self, html: str) -> List[int]:
        """Parse list of round numbers from HTML."""
        pass

    @abstractmethod
    def fetch_round_url(self, base_url: str, round_number: int) -> str:
        """Fetch a specific round's HTML."""
        pass

    @abstractmethod
    def parse_round_pairings(self, html: str, round_number: int) -> List[dict]:
        """Parse pairings from a round's HTML."""
        pass


class SchackSeScraper(BaseScraper):
    """Scraper for Swedish Chess Federation (member.schack.se) tournaments."""

    BASE_URL = "https://member.schack.se"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

    def fetch_tournament_url(self, url: str) -> str:
        """Fetch the tournament page HTML."""
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.text

    def parse_tournament_name(self, html: str) -> str:
        """Parse the tournament name from HTML."""
        soup = BeautifulSoup(html, "lxml")

        h4 = soup.find("h4", class_="header")
        if h4:
            return h4.get_text(strip=True)

        title = soup.find("title")
        if title:
            return title.get_text(strip=True)

        return "Unknown Tournament"

    def extract_tournament_id(self, url: str) -> Optional[str]:
        """Extract tournament ID from URL."""
        match = re.search(r"id=(\d+)", url)
        if match:
            return match.group(1)
        return None

    def parse_rounds(self, html: str) -> List[int]:
        """Parse list of round numbers from the main tournament page."""
        soup = BeautifulSoup(html, "lxml")
        rounds = []

        for link in soup.find_all(
            "a", href=re.compile(r"ShowTournamentGroupMatchesServlet")
        ):
            href = link.get("href", "")
            match = re.search(r"round=(\d+)", href)
            if match:
                rounds.append(int(match.group(1)))

        return sorted(set(rounds))

    def fetch_round_url(self, base_url: str, round_number: int) -> str:
        """Fetch a specific round's HTML."""
        tournament_id = self.extract_tournament_id(base_url)
        if not tournament_id:
            raise ValueError("Could not extract tournament ID from URL")

        round_url = f"{self.BASE_URL}/ShowTournamentGroupMatchesServlet?id={tournament_id}&round={round_number}"
        response = self.session.get(round_url, timeout=30)
        response.raise_for_status()
        return response.text

    def parse_round_pairings(self, html: str, round_number: int) -> List[dict]:
        """
        Parse pairings from a round's HTML.

        Returns a list of dicts with keys:
        - participant1: name of first participant/team
        - participant2: name of second participant/team
        - board_number: optional board number
        - score1: optional score for participant 1
        - score2: optional score for participant 2
        """
        soup = BeautifulSoup(html, "lxml")
        pairings = []

        match_tables = soup.find_all("table", class_="greyproptable")

        for table in match_tables:
            rows = table.find_all("tr")
            for row in rows:
                header_cells = row.find_all("td", class_="listheader")
                result_cells = row.find_all("td", class_="listheadercenter")

                if len(header_cells) >= 2 and result_cells:
                    team1 = header_cells[0].get_text(strip=True)
                    team2 = header_cells[1].get_text(strip=True)
                    result_text = result_cells[0].get_text(strip=True)

                    if not team1 or not team2:
                        continue

                    score1, score2 = self._parse_result(result_text)

                    pairings.append(
                        {
                            "participant1": team1,
                            "participant2": team2,
                            "board_number": None,
                            "score1": score1,
                            "score2": score2,
                        }
                    )

        return pairings

    def _parse_result(
        self, result_text: str
    ) -> tuple[Optional[float], Optional[float]]:
        """Parse a result string like '3 - 1' or '3½ - ½' into scores."""
        result_text = result_text.replace("½", "0.5").replace(" ", "")

        match = re.match(r"([\d.]+)\s*-\s*([\d.]+)", result_text)
        if match:
            try:
                score1 = float(match.group(1))
                score2 = float(match.group(2))
                return score1, score2
            except ValueError:
                pass

        return None, None

    def fetch_all_rounds(self, url: str) -> tuple[str, List[int]]:
        """
        Fetch tournament name and all available round numbers.
        """
        html = self.fetch_tournament_url(url)
        name = self.parse_tournament_name(html)
        rounds = self.parse_rounds(html)
        return name, rounds

    def fetch_round_pairings(self, base_url: str, round_number: int) -> List[dict]:
        """Fetch and parse pairings for a specific round."""
        html = self.fetch_round_url(base_url, round_number)
        return self.parse_round_pairings(html, round_number)
