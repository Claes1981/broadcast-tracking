"""API-based scraper for Swedish Chess Federation (member.schack.se).

Uses the REST API at /public/api/v1/ endpoints instead of HTML scraping.
More reliable for individual tournaments where round links are loaded via JavaScript.

API endpoints:
- Group info:    GET /public/api/v1/tournament/group/id/{id}
- Individual:    GET /public/api/v1/tournamentresults/roundresults/id/{id}
- Team:          GET /public/api/v1/tournamentresults/team/roundresults/id/{id}
- Player:        GET /public/api/v1/player/{id}/date/{date}
- Club:          GET /public/api/v1/organisation/club/{id}
"""

import json
import re

import requests
from .base import BaseScraper


class SchackSeApiScraper(BaseScraper):
    """Scraper that uses the member.schack.se REST API.

    The API returns all round results in a single call, so the scraper
    caches the full response and filters by round number on demand.

    Name resolution:
    - Individual tournaments (team_number == -1): look up player name
    - Team tournaments (team_number > 0): look up club name + team number
    """

    BASE_URL = "https://member.schack.se"
    API_PREFIX = "/public/api/v1"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                ),
                "Accept": "application/json",
            }
        )
        self._player_cache: dict[int, str] = {}
        self._club_cache: dict[int, str] = {}
        self._tournament_id: int | None = None
        self._is_team_tournament: bool | None = None
        self._all_results: list[dict] | None = None
        self._group_info: dict | None = None

    # -- BaseScraper abstract methods --

    def fetch_tournament_url(self, url: str) -> str:
        """Fetch tournament data via API. Returns group info JSON string."""
        self._tournament_id = self._extract_tournament_id(url)
        if self._tournament_id is None:
            raise ValueError("Could not extract tournament ID from URL")

        group_url = (
            f"{self.BASE_URL}{self.API_PREFIX}"
            f"/tournament/group/id/{self._tournament_id}"
        )
        response = self.session.get(group_url, timeout=30)
        response.raise_for_status()
        self._group_info = response.json()
        return response.text

    def parse_tournament_name(self, html: str) -> str:
        """Parse tournament name from group info JSON.

        Tries group name first, then falls back to rootClasses className.
        """
        data = self._group_info or json.loads(html)
        if "name" in data and data["name"]:
            return data["name"]

        if "rootClasses" in data and data["rootClasses"]:
            class_name = data["rootClasses"][0].get("className", "")
            if class_name:
                return class_name

        return "Unknown Tournament"

    def parse_rounds(self, html: str) -> list[int]:
        """Extract round numbers from the API results.

        Fetches the appropriate endpoint (individual or team) and extracts
        unique round numbers. Caches the full response for later use.
        """
        if self._tournament_id is None:
            return []

        results = self._fetch_all_results()
        self._all_results = results
        return sorted({entry["roundNr"] for entry in results})

    def fetch_round_url(self, base_url: str, round_number: int) -> str:
        """Return cached results JSON filtered to the requested round.

        The API returns all rounds at once, so we cache the full response
        and filter by round number here.
        """
        if self._all_results is None:
            self._all_results = self._fetch_all_results()

        round_results = [r for r in self._all_results if r["roundNr"] == round_number]
        return json.dumps(round_results)

    def parse_round_pairings(self, html: str, round_number: int) -> list[dict]:
        """Parse pairings from round results JSON.

        Returns list of dicts with keys:
        - participant1, participant2, board_number, score1, score2
        """
        results = json.loads(html)
        pairings = []

        for entry in results:
            home_id = entry["homeId"]
            home_team = entry.get("homeTeamNumber", -1)
            away_id = entry["awayId"]
            away_team = entry.get("awayTeamNumber", -1)

            p1_name = self._resolve_name(home_id, home_team)
            p2_name = self._resolve_name(away_id, away_team)

            pairings.append(
                self._build_pairing_dict(
                    team1=p1_name,
                    team2=p2_name,
                    board_number=entry.get("board"),
                    score1=entry.get("homeResult"),
                    score2=entry.get("awayResult"),
                )
            )

        return pairings

    # -- Internal helpers --

    @staticmethod
    def _extract_tournament_id(url: str) -> int | None:
        """Extract tournament ID from URL."""
        match = re.search(r"id=(\d+)", url)
        return int(match.group(1)) if match else None

    def _fetch_all_results(self) -> list[dict]:
        """Fetch all round results via API.

        Tries individual endpoint first, falls back to team endpoint.
        """
        if self._tournament_id is None:
            return []

        # Try individual tournament endpoint
        url = (
            f"{self.BASE_URL}{self.API_PREFIX}"
            f"/tournamentresults/roundresults/id/{self._tournament_id}"
        )
        response = self.session.get(url, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                self._is_team_tournament = False
                return data

        # Fall back to team tournament endpoint
        url = (
            f"{self.BASE_URL}{self.API_PREFIX}"
            f"/tournamentresults/team/roundresults/id/{self._tournament_id}"
        )
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        self._is_team_tournament = True
        return data

    def _resolve_name(self, entity_id: int, team_number: int = -1) -> str:
        """Resolve a player or club ID to its display name.

        For individual tournaments (team_number == -1): look up player name.
        For team tournaments (team_number > 0): look up club name + team number.
        """
        if team_number > 0:
            return self._resolve_club_name(entity_id, team_number)
        return self._resolve_player_name(entity_id)

    def _resolve_player_name(self, player_id: int) -> str:
        """Look up player name by ID, with caching."""
        if player_id in self._player_cache:
            return self._player_cache[player_id]

        url = f"{self.BASE_URL}{self.API_PREFIX}/player/{player_id}/date/2026-01-01"
        response = self.session.get(url, timeout=30)

        if response.status_code == 200:
            data = response.json()
            name = f"{data['firstName']} {data['lastName']}"
        else:
            name = f"Player {player_id}"

        self._player_cache[player_id] = name
        return name

    def _resolve_club_name(self, club_id: int, team_number: int) -> str:
        """Look up club name by ID, with caching."""
        if club_id in self._club_cache:
            club_name = self._club_cache[club_id]
        else:
            url = f"{self.BASE_URL}{self.API_PREFIX}/organisation/club/{club_id}"
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                club_name = response.json().get("name", f"Club {club_id}")
            else:
                club_name = f"Club {club_id}"

            self._club_cache[club_id] = club_name

        return f"{club_name} {team_number}"

    @staticmethod
    def _build_pairing_dict(
        team1: str,
        team2: str,
        board_number: int | None = None,
        score1: float | None = None,
        score2: float | None = None,
    ) -> dict:
        """Build a pairing dict matching the BaseScraper contract."""
        return {
            "participant1": team1,
            "participant2": team2,
            "board_number": board_number,
            "score1": score1,
            "score2": score2,
        }
