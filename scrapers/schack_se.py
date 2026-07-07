from bs4 import BeautifulSoup
import requests
import re
from config import SCRAPER_USER_AGENT
from .base import BaseScraper


class SchackSeScraper(BaseScraper):
    """Scraper for Swedish Chess Federation (member.schack.se) tournaments."""

    BASE_URL = "https://member.schack.se"

    # Method 3: Headerless team tournament cell indices
    HEADERLESS_MIN_CELLS = 17
    CELL_HOME_TEAM = 4
    CELL_SEPARATOR = 8
    CELL_AWAY_TEAM = 12
    CELL_RESULT = 16

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": SCRAPER_USER_AGENT})

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

    def extract_tournament_id(self, url: str) -> str | None:
        """Extract tournament ID from URL."""
        match = re.search(r"id=(\d+)", url)
        if match:
            return match.group(1)
        return None

    def parse_rounds(self, html: str) -> list[int]:
        """Parse list of round numbers from the main tournament page.

        Handles both individual tournaments (ShowTournamentGroupMatchesServlet links)
        and team tournaments (ShowTournamentServlet links or round numbers in tables).
        """
        soup = BeautifulSoup(html, "lxml")
        rounds = []

        # Method 1: ShowTournamentGroupMatchesServlet links (individual tournaments)
        for link in soup.find_all(
            "a", href=re.compile(r"ShowTournamentGroupMatchesServlet")
        ):
            href = link.get("href", "")
            match = re.search(r"round=(\d+)", href)
            if match:
                rounds.append(int(match.group(1)))

        # Method 2: ShowTournamentServlet links with round= param (team tournaments)
        for link in soup.find_all("a", href=re.compile(r"ShowTournamentServlet")):
            href = link.get("href", "")
            match = re.search(r"round=(\d+)", href)
            if match:
                rounds.append(int(match.group(1)))

        # Method 3: Round numbers in table cells (team tournaments)
        if not rounds:
            tables = soup.find_all("table")
            for table in tables:
                headers = table.find_all(
                    ["th", "td"], class_=re.compile(r"header|center", re.IGNORECASE)
                )
                for header in headers:
                    text = header.get_text(strip=True)
                    if text in ("RONDA", "ROND"):
                        rows = table.find_all("tr")
                        for row in rows:
                            cells = row.find_all("td")
                            if cells:
                                cell_text = cells[0].get_text(strip=True)
                                try:
                                    round_num = int(cell_text)
                                    rounds.append(round_num)
                                except ValueError:
                                    pass

        return sorted(set(rounds))

    def fetch_round_url(self, base_url: str, round_number: int) -> str:
        """Fetch a specific round's HTML.

        Tries ShowTournamentGroupMatchesServlet first (individual tournaments),
        then falls back to ShowTournamentServlet (team tournaments).
        """
        tournament_id = self.extract_tournament_id(base_url)
        if not tournament_id:
            raise ValueError("Could not extract tournament ID from URL")

        # Try individual tournament URL first
        round_url = f"{self.BASE_URL}/ShowTournamentGroupMatchesServlet?id={tournament_id}&round={round_number}"
        response = self.session.get(round_url, timeout=30)

        # Fall back to team tournament URL
        if response.status_code == 404:
            round_url = f"{self.BASE_URL}/ShowTournamentServlet?id={tournament_id}&round={round_number}"
            response = self.session.get(round_url, timeout=30)

        response.raise_for_status()
        return response.text

    def parse_round_pairings(self, html: str, round_number: int) -> list[dict]:
        """
        Parse pairings from a round's HTML.

        Handles both individual tournaments (greyproptable with listheader cells)
        and team tournaments (tables with HEMMALAG/BORTALAG columns).

        Returns a list of dicts with keys:
        - participant1: name of first participant/team
        - participant2: name of second participant/team
        - board_number: optional board number
        - score1: optional score for participant 1
        - score2: optional score for participant 2
        """
        soup = BeautifulSoup(html, "lxml")
        pairings = []

        # Method 1: Individual tournament format (greyproptable)
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

                    # Skip if team2 looks like an Elo rating (E followed by digits)
                    if team2.startswith("E") and team2[1:].isdigit():
                        continue

                    pairings.append(self._build_pairing_dict(team1, team2, result_text))

        # Method 2: Team tournament format (HEMMALAG vs BORTALAG headers)
        if not pairings:
            for table in soup.find_all("table"):
                header_row = table.find("tr")
                if not header_row:
                    continue

                th_cells = header_row.find_all(["th", "td"])
                header_map = {}
                for idx, cell in enumerate(th_cells):
                    text = cell.get_text(strip=True).upper()
                    if text and text not in header_map:
                        header_map[text] = idx

                if "HEMMALAG" not in header_map or "BORTALAG" not in header_map:
                    continue

                home_idx = header_map["HEMMALAG"]
                away_idx = header_map["BORTALAG"]
                result_idx = header_map.get("RESULTAT", max(home_idx, away_idx) + 1)

                rows = table.find_all("tr")
                for row in rows[1:]:  # skip header row
                    cells = row.find_all("td")
                    if len(cells) <= max(home_idx, away_idx, result_idx):
                        continue

                    team1 = cells[home_idx].get_text(strip=True)
                    team2 = cells[away_idx].get_text(strip=True)
                    result_text = cells[result_idx].get_text(strip=True)

                    if not team1 or not team2:
                        continue

                    pairings.append(self._build_pairing_dict(team1, team2, result_text))

        # Method 3: Headerless team tournament (nested tables, fixed cell positions)
        # Structure: C4=home team, C6=home Elo, C8="-", C12=away team, C14=away Elo, C16=result
        if not pairings:
            for table in soup.find_all("table"):
                rows = table.find_all("tr")
                if len(rows) < 2:
                    continue

                # Only process the first row of each match table (team header row)
                row = rows[0]
                cells = row.find_all("td")
                if len(cells) < self.HEADERLESS_MIN_CELLS:
                    continue

                separator = cells[self.CELL_SEPARATOR].get_text(strip=True)
                if separator != "-":
                    continue

                team1 = cells[self.CELL_HOME_TEAM].get_text(strip=True)
                team2 = cells[self.CELL_AWAY_TEAM].get_text(strip=True)
                result_text = cells[self.CELL_RESULT].get_text(strip=True)

                if not team1 or not team2:
                    continue

                pairings.append(self._build_pairing_dict(team1, team2, result_text))

        return pairings

    def _build_pairing_dict(
        self,
        team1: str,
        team2: str,
        result_text: str,
    ) -> dict:
        """Build a pairing dict from team names and result text."""
        score1, score2 = self._parse_result(result_text)
        return {
            "participant1": team1,
            "participant2": team2,
            "board_number": None,
            "score1": score1,
            "score2": score2,
        }

    def _parse_result(self, result_text: str) -> tuple[float | None, float | None]:
        """Parse a result string like '3 - 1' or '3½ - ½' into scores."""
        result_text = result_text.replace(" ", "").replace("½", ".5")

        match = re.match(r"([\d.]+)\s*-\s*([\d.]+)", result_text)
        if match:
            try:
                score1 = float(match.group(1))
                score2 = float(match.group(2))
                return score1, score2
            except ValueError:
                pass

        return None, None
