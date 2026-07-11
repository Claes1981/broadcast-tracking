"""Scraper for Chess-Results.com tournaments.

Scrapes board pairings (art=2) from both individual and team tournaments.
Team tournaments are detected by checking if the pairings table has 6 columns
(team format) instead of 16 columns (individual format).
"""

from contextlib import suppress
import re
from typing import cast

from bs4 import BeautifulSoup, Tag
import requests


from config import SCRAPER_USER_AGENT
from .base import BaseScraper


class ChessResultsScraper(BaseScraper):
    """Scraper for Chess-Results.com tournaments.

    Parses board pairings tables (art=2) from HTML pages.
    Handles both individual tournaments (16-column table) and
    team tournaments (6-column table).
    """

    BASE_URL = "https://chess-results.com"

    # Individual tournament pairings table minimum cells
    INDIVIDUAL_MIN_CELLS = 13

    # Team tournament pairings table column indices
    TEAM_HOME = 1
    TEAM_AWAY = 2
    TEAM_RES_HOME = 3
    TEAM_RES_AWAY = 5
    TEAM_MIN_CELLS = 6

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": SCRAPER_USER_AGENT})
        self._tournament_id: int | None = None
        self._is_team_tournament: bool | None = None

    # -- BaseScraper abstract methods --

    def fetch_tournament_url(self, url: str) -> str:
        """Fetch the tournament page HTML."""
        self._tournament_id = self._extract_tournament_id(url)
        if self._tournament_id is None:
            raise ValueError("Could not extract tournament ID from URL")
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return response.text

    def parse_tournament_name(self, html: str) -> str:
        """Parse the tournament name from HTML.

        Tries H2 element first (e.g., '9. Open Bohumín 2026 "A" - "Master"'),
        then falls back to page title.
        """
        soup = BeautifulSoup(html, "lxml")

        # Try H2 element
        h2 = soup.find("h2")
        if h2:
            text = h2.get_text(strip=True)
            if text:
                return text

        # Fall back to page title (strip "Chess-Results Server ..." prefix)
        title = soup.find("title")
        if title:
            text = title.get_text(strip=True)
            # Remove "Chess-Results Server ..." prefix
            # Formats:
            #   "Chess-Results Server Chess-results.com - Belgian Open 2026"
            #   "Chess-Results Server - Tournament Name"
            text = re.sub(r"^Chess-Results[^-]*-\s*", "", text, count=1)
            # If still has a trailing "something - " prefix (e.g. "results.com - ")
            # strip one more segment
            text = re.sub(r"^[^-]+-\s*", "", text, count=1)
            return text.strip()

        return "Unknown Tournament"

    def parse_rounds(self, html: str) -> list[int]:
        """Parse list of round numbers from the main tournament page.

        Looks for board pairings links (art=2) with rd= parameter.
        """
        soup = BeautifulSoup(html, "lxml")
        rounds = []

        for link in soup.find_all("a", href=re.compile(r"art=2")):
            href = cast(str, link.get("href", ""))
            match = re.search(r"rd=(\d+)", href)
            if match:
                with suppress(ValueError):
                    rounds.append(int(match.group(1)))

        return sorted(set(rounds))

    def fetch_round_url(self, base_url: str, round_number: int) -> str:
        """Fetch a specific round's board pairings HTML (art=2).

        Constructs URL from cached tournament ID.
        """
        if self._tournament_id is None:
            self._tournament_id = self._extract_tournament_id(base_url)
            if self._tournament_id is None:
                raise ValueError("Could not extract tournament ID from URL")

        round_url = (
            f"{self.BASE_URL}/tnr{self._tournament_id}.aspx?"
            f"lan=1&art=2&rd={round_number}&turdet=YES&flag=30"
        )
        response = self.session.get(round_url, timeout=30)
        response.raise_for_status()
        return response.text

    def parse_round_pairings(self, html: str, round_number: int) -> list[dict]:
        """Parse pairings from a round's board pairings HTML.

        Handles both individual tournaments (16-column table) and
        team tournaments (6-column table).

        Returns a list of dicts with keys:
        - participant1: name of first participant/team
        - participant2: name of second participant/team
        - board_number: optional board number
        - score1: optional score for participant 1
        - score2: optional score for participant 2
        """
        soup = BeautifulSoup(html, "lxml")
        pairings = []

        # Find the pairings table - it's the table with the round header
        # For individual: 16 columns starting with "Bo.", "No.", etc.
        # For team: 6 columns starting with "No.", "Team", "Team", etc.
        pairings_table = self._find_pairings_table(soup)
        if pairings_table is None:
            return []

        rows = pairings_table.find_all("tr")
        if not rows:
            return []

        # Detect format from first data row (skip header rows)
        first_data_row = None
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= self.TEAM_MIN_CELLS:
                first_data_row = row
                break

        if first_data_row is None:
            return []

        num_cells = len(first_data_row.find_all("td"))

        if num_cells >= self.INDIVIDUAL_MIN_CELLS:
            # Individual tournament format
            self._is_team_tournament = False
            # Detect column layout from header row
            layout = self._detect_individual_layout(pairings_table)
            pairings = self._parse_individual_pairings(rows, layout)
        elif num_cells >= self.TEAM_MIN_CELLS:
            # Team tournament format
            self._is_team_tournament = True
            pairings = self._parse_team_pairings(rows)

        return pairings

    # -- Internal helpers --

    @staticmethod
    def _extract_tournament_id(url: str) -> int | None:
        """Extract tournament ID from a Chess-Results URL."""
        match = re.search(r"tnr(\d+)", url)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    def _find_pairings_table(self, soup: BeautifulSoup) -> Tag | None:
        """Find the pairings data table in the HTML.

        The pairings table is typically the last large table on the page
        (Table 6 in the HTML structure), containing the actual pairing data.
        """
        tables = soup.find_all("table")

        # Look for a table with a header row containing typical pairing columns
        for table in reversed(tables):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            header_row = rows[0]
            cells = header_row.find_all(["td", "th"])
            header_texts = [c.get_text(strip=True) for c in cells]

            # Individual: header contains "Bo." or "White"
            # Team: header contains "Team" appearing twice
            team_count = sum(1 for t in header_texts if t == "Team")
            has_board = any(t in ("Bo.", "Board") for t in header_texts)
            has_white = "White" in header_texts

            if (
                team_count == 2
                or has_white
                or (has_board and len(cells) >= self.INDIVIDUAL_MIN_CELLS)
            ):
                return cast(Tag, table)

        # Fallback: return the last table with enough rows
        for table in reversed(tables):
            if len(table.find_all("tr")) > 2:
                return cast(Tag, table)

        return None

    @staticmethod
    def _detect_individual_layout(table: Tag) -> tuple[int, int, int, int]:
        """Detect column layout from the pairings table header.

        Chess-Results.com has two individual tournament formats:
        - Wide format (16 cols): Bo|No| |WhTitle|White|Rtg|Pts|Result|Pts|BlTitle|Black|Rtg| |No|PGN
        - Narrow format (13 cols): Bo|No|WhTitle|White|Rtg|Pts|Result|Pts|BlTitle|Black|Rtg|No|PGN

        Returns (white_title, white_name, result, black_title) column indices.
        Uses "White" and "Black" header labels to find name columns.
        """
        rows = table.find_all("tr")
        if not rows:
            return (2, 3, 6, 8)  # fallback to narrow format

        header_row = rows[0]
        cells = header_row.find_all(["td", "th"])
        header_texts = [c.get_text(strip=True) for c in cells]

        # Find "White" and "Black" columns in header
        white_idx = header_texts.index("White") if "White" in header_texts else -1
        black_idx = header_texts.index("Black") if "Black" in header_texts else -1

        if white_idx < 0 or black_idx < 0:
            return (2, 3, 6, 8)  # fallback

        # Title is column before name, result is 3 columns after name
        # (White|Rtg|Pts|Result = idx, idx+1, idx+2, idx+3)
        white_title = white_idx - 1
        black_title = black_idx - 1
        result = white_idx + 3

        return (white_title, white_idx, result, black_title)

    def _parse_individual_pairings(
        self,
        rows: list,
        layout: tuple[int, int, int, int],
    ) -> list[dict]:
        """Parse individual tournament pairings from table rows.

        Layout is (white_title, white_name, result, black_title) detected
        from the table header by _detect_individual_layout.
        black_name is always black_title + 1.
        """
        white_title_col, white_name_col, result_col, black_title_col = layout
        black_name_col = black_title_col + 1
        pairings = []

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < self.INDIVIDUAL_MIN_CELLS:
                continue

            # Skip header rows
            first_cell = cells[0].get_text(strip=True)
            if first_cell in ("Bo.", "Board", "") and len(cells) > 1:
                second_cell = cells[1].get_text(strip=True)
                if second_cell in ("No.", ""):
                    continue

            white_title = cells[white_title_col].get_text(strip=True)
            white_name = cells[white_name_col].get_text(strip=True)
            black_title = cells[black_title_col].get_text(strip=True)
            black_name = cells[black_name_col].get_text(strip=True)

            # Combine title with name: "FM Holeksa, Zdenek"
            white_display = f"{white_title} {white_name}" if white_title else white_name
            black_display = f"{black_title} {black_name}" if black_title else black_name

            # Skip not-paired rows
            if not white_name or black_name == "not paired":
                continue

            # Board number from first cell
            board_number = self._parse_board_number(first_cell)

            # Parse result
            result_text = cells[result_col].get_text(strip=True)
            score1, score2 = self._parse_individual_result(result_text)

            pairings.append(
                self._build_pairing_dict(
                    team1=white_display,
                    team2=black_display,
                    board_number=board_number,
                    score1=score1,
                    score2=score2,
                )
            )

        return pairings

    def _parse_team_pairings(self, rows: list) -> list[dict]:
        """Parse team tournament pairings from table rows.

        Table format (6 columns):
        No. | Team (home) | Team (away) | Res. | : | Res.
        0    1             2              3       4   5
        """
        pairings = []

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < self.TEAM_MIN_CELLS:
                continue

            # Skip header row
            first_cell = cells[0].get_text(strip=True)
            if first_cell == "No.":
                continue

            home_team = cells[self.TEAM_HOME].get_text(strip=True)
            away_team = cells[self.TEAM_AWAY].get_text(strip=True)

            if not home_team or not away_team:
                continue

            # Board number from first cell (match number)
            board_number = self._parse_board_number(first_cell)

            # Parse result
            home_res = cells[self.TEAM_RES_HOME].get_text(strip=True)
            away_res = cells[self.TEAM_RES_AWAY].get_text(strip=True)
            score1, score2 = self._parse_team_result(home_res, away_res)

            pairings.append(
                self._build_pairing_dict(
                    team1=home_team,
                    team2=away_team,
                    board_number=board_number,
                    score1=score1,
                    score2=score2,
                )
            )

        return pairings

    @staticmethod
    def _parse_board_number(text: str) -> int | None:
        """Parse board number from a cell text."""
        try:
            return int(text)
        except ValueError:
            return None

    @staticmethod
    def _parse_individual_result(result_text: str) -> tuple[float | None, float | None]:
        """Parse individual tournament result.

        Handles full format "X - Y" (e.g., "0 - 1", "½ - ½") and
        single value format (e.g., "1", "0", "½").
        Also handles fractional notation ⅓ and ⅔.
        """
        if not result_text or result_text == "-":
            return None, None

        # Handle "X - Y" format (e.g., "0 - 1", "½ - ½")
        if " - " in result_text:
            parts = result_text.split(" - ", 1)
            white_score = ChessResultsScraper._parse_single_score(parts[0].strip())
            black_score = ChessResultsScraper._parse_single_score(parts[1].strip())
            return white_score, black_score

        # Single value format: white's score, black gets (1 - white)
        result_text = (
            result_text.replace("½", "0.5").replace("⅓", "0.33").replace("⅔", "0.67")
        )

        try:
            white_score = float(result_text)
            black_score = round(1.0 - white_score, 2)
            return white_score, black_score
        except ValueError:
            return None, None

    @staticmethod
    def _parse_single_score(score_text: str) -> float | None:
        """Parse a single score value, handling fractional notation.

        Uses ".5" suffix for halves (not "0.5") to avoid "2½" → "20.5".
        """
        if not score_text:
            return None
        score_text = (
            score_text.replace("½", ".5").replace("⅓", "0.33").replace("⅔", "0.67")
        )
        try:
            return float(score_text)
        except ValueError:
            return None

    @staticmethod
    def _parse_team_result(
        home_res: str, away_res: str
    ) -> tuple[float | None, float | None]:
        """Parse team tournament result from two separate score cells.

        Uses _parse_single_score which handles "½" → ".5" correctly
        (avoids "2½" → "20.5" digit concatenation).
        """
        score1 = ChessResultsScraper._parse_single_score(home_res) if home_res else None
        score2 = ChessResultsScraper._parse_single_score(away_res) if away_res else None
        return score1, score2

    @staticmethod
    def _build_pairing_dict(
        team1: str,
        team2: str,
        board_number: int | None = None,
        score1: float | None = None,
        score2: float | None = None,
    ) -> dict:
        """Build a pairing dict from team/player names and result."""
        return {
            "participant1": team1,
            "participant2": team2,
            "board_number": board_number,
            "score1": score1,
            "score2": score2,
        }
