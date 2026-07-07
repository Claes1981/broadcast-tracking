"""Tests for SchackSeApiScraper (API-based scraping).

Covers both individual and team tournament endpoints,
name resolution (players and clubs), and edge cases.
"""

import json
import pytest
from unittest.mock import Mock, patch

from scrapers.schack_se_api import SchackSeApiScraper


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def api_scraper():
    """Create a fresh API scraper instance."""
    return SchackSeApiScraper()


# ============================================================================
# URL PARSING
# ============================================================================


class TestExtractTournamentId:
    """Tests for tournament ID extraction from URLs."""

    def test_extract_id_from_standard_url(self, api_scraper):
        """Test extracting ID from standard member.schack.se URL."""
        tid = api_scraper._extract_tournament_id(
            "https://member.schack.se/ShowTournamentServlet?id=17803"
        )
        assert tid == 17803

    def test_extract_id_from_short_url(self, api_scraper):
        """Test extracting ID from shortened URL."""
        tid = api_scraper._extract_tournament_id("https://member.schack.se?id=42")
        assert tid == 42

    def test_extract_id_returns_none_for_invalid_url(self, api_scraper):
        """Test that invalid URL returns None."""
        assert api_scraper._extract_tournament_id("https://example.com") is None
        assert api_scraper._extract_tournament_id("https://member.schack.se") is None
        assert api_scraper._extract_tournament_id("") is None

    def test_fetch_tournament_url_raises_for_invalid_url(self, api_scraper):
        """Test that fetch_tournament_url raises ValueError for bad URL."""
        with pytest.raises(ValueError, match="Could not extract tournament ID"):
            api_scraper.fetch_tournament_url("https://example.com")


# ============================================================================
# TOURNAMENT NAME PARSING
# ============================================================================


class TestParseTournamentName:
    """Tests for tournament name parsing from group info JSON."""

    def test_parse_name_from_group_info(self, api_scraper):
        """Test parsing name directly from group info."""
        group_info = {"name": "Veteran-SM i snabbschack 2026"}
        api_scraper._group_info = group_info

        name = api_scraper.parse_tournament_name(json.dumps(group_info))
        assert name == "Veteran-SM i snabbschack 2026"

    def test_parse_name_from_root_classes(self, api_scraper):
        """Test parsing name from rootClasses when group name is empty."""
        group_info = {
            "name": "",
            "rootClasses": [{"classID": 7259, "className": "Veteran-SM i snabbschack"}],
        }
        api_scraper._group_info = group_info

        name = api_scraper.parse_tournament_name(json.dumps(group_info))
        assert name == "Veteran-SM i snabbschack"

    def test_parse_name_returns_unknown(self, api_scraper):
        """Test fallback to 'Unknown Tournament'."""
        group_info = {"name": "", "rootClasses": []}
        api_scraper._group_info = group_info

        name = api_scraper.parse_tournament_name(json.dumps(group_info))
        assert name == "Unknown Tournament"

    def test_parse_name_uses_group_info_cache(self, api_scraper):
        """Test that cached _group_info is used when available."""
        api_scraper._group_info = {"name": "Cached Name"}
        # Even with different html argument, cached info takes priority
        name = api_scraper.parse_tournament_name(json.dumps({"name": "Other"}))
        assert name == "Cached Name"


# ============================================================================
# ROUND EXTRACTION
# ============================================================================


class TestParseRounds:
    """Tests for round number extraction from API results."""

    def test_parse_rounds_individual(self, api_scraper):
        """Test extracting rounds from individual tournament results."""
        api_scraper._tournament_id = 17803

        mock_results = [
            {"roundNr": 1, "board": 1, "homeId": 100, "awayId": 200},
            {"roundNr": 2, "board": 1, "homeId": 200, "awayId": 300},
            {"roundNr": 1, "board": 2, "homeId": 300, "awayId": 400},
            {"roundNr": 3, "board": 1, "homeId": 100, "awayId": 300},
        ]

        with patch.object(api_scraper, "_fetch_all_results", return_value=mock_results):
            rounds = api_scraper.parse_rounds("")
            assert rounds == [1, 2, 3]

    def test_parse_rounds_team(self, api_scraper):
        """Test extracting rounds from team tournament results."""
        api_scraper._tournament_id = 17852

        mock_results = [
            {"roundNr": 1, "board": -1000, "homeId": 1, "awayId": 2},
            {"roundNr": 2, "board": -1000, "homeId": 2, "awayId": 3},
        ]

        with patch.object(api_scraper, "_fetch_all_results", return_value=mock_results):
            rounds = api_scraper.parse_rounds("")
            assert rounds == [1, 2]

    def test_parse_rounds_returns_empty_when_no_tournament_id(self, api_scraper):
        """Test that parse_rounds returns empty list without tournament ID."""
        api_scraper._tournament_id = None
        rounds = api_scraper.parse_rounds("")
        assert rounds == []

    def test_parse_rounds_caches_results(self, api_scraper):
        """Test that parse_rounds caches results for later use."""
        api_scraper._tournament_id = 17803
        mock_results = [
            {"roundNr": 1, "board": 1, "homeId": 100, "awayId": 200},
        ]

        with patch.object(api_scraper, "_fetch_all_results", return_value=mock_results):
            api_scraper.parse_rounds("")
            assert api_scraper._all_results == mock_results


# ============================================================================
# FETCH ROUND URL
# ============================================================================


class TestFetchRoundUrl:
    """Tests for fetching specific round data."""

    def test_fetch_round_url_filters_by_round(self, api_scraper):
        """Test that fetch_round_url returns only the requested round."""
        api_scraper._all_results = [
            {"roundNr": 1, "board": 1, "homeId": 100, "awayId": 200},
            {"roundNr": 2, "board": 1, "homeId": 200, "awayId": 100},
            {"roundNr": 2, "board": 2, "homeId": 300, "awayId": 400},
        ]

        result = api_scraper.fetch_round_url("https://member.schack.se?id=123", 2)
        data = json.loads(result)
        assert len(data) == 2
        assert all(entry["roundNr"] == 2 for entry in data)

    def test_fetch_round_url_fetches_if_not_cached(self, api_scraper):
        """Test that fetch_round_url fetches results if not cached."""
        api_scraper._tournament_id = 17803
        api_scraper._all_results = None

        mock_results = [
            {"roundNr": 1, "board": 1, "homeId": 100, "awayId": 200},
        ]

        with patch.object(api_scraper, "_fetch_all_results", return_value=mock_results):
            result = api_scraper.fetch_round_url("https://member.schack.se?id=123", 1)
            data = json.loads(result)
            assert len(data) == 1
            assert api_scraper._all_results == mock_results

    def test_fetch_round_url_empty_when_no_matching_round(self, api_scraper):
        """Test that non-existent round returns empty JSON array."""
        api_scraper._all_results = [
            {"roundNr": 1, "board": 1, "homeId": 100, "awayId": 200},
        ]

        result = api_scraper.fetch_round_url("https://member.schack.se?id=123", 99)
        data = json.loads(result)
        assert data == []


# ============================================================================
# PAIRING PARSING
# ============================================================================


class TestParseRoundPairings:
    """Tests for parsing pairings from round results JSON."""

    def test_parse_individual_pairings(self, api_scraper):
        """Test parsing individual tournament pairings."""
        round_data = [
            {
                "roundNr": 1,
                "board": 1,
                "homeId": 348550,
                "homeTeamNumber": -1,
                "awayId": 362076,
                "awayTeamNumber": -1,
                "homeResult": 0.0,
                "awayResult": 1.0,
            },
            {
                "roundNr": 1,
                "board": 2,
                "homeId": 362075,
                "homeTeamNumber": -1,
                "awayId": 408934,
                "awayTeamNumber": -1,
                "homeResult": 1.0,
                "awayResult": 0.0,
            },
        ]

        # Mock player lookups
        with patch.object(api_scraper, "_resolve_player_name") as mock_player:
            mock_player.side_effect = lambda pid: f"Player {pid}"

            pairings = api_scraper.parse_round_pairings(json.dumps(round_data), 1)

        assert len(pairings) == 2
        assert pairings[0]["participant1"] == "Player 348550"
        assert pairings[0]["participant2"] == "Player 362076"
        assert pairings[0]["board_number"] == 1
        assert pairings[0]["score1"] == 0.0
        assert pairings[0]["score2"] == 1.0
        assert pairings[1]["board_number"] == 2

    def test_parse_team_pairings(self, api_scraper):
        """Test parsing team tournament pairings."""
        round_data = [
            {
                "roundNr": 1,
                "board": -1000,
                "homeId": 38345,
                "homeTeamNumber": 2,
                "awayId": 38429,
                "awayTeamNumber": 1,
                "homeResult": 0.0,
                "awayResult": 6.0,
            },
        ]

        with patch.object(api_scraper, "_resolve_club_name") as mock_club:
            mock_club.side_effect = lambda cid, tn: f"Club {cid} {tn}"

            pairings = api_scraper.parse_round_pairings(json.dumps(round_data), 1)

        assert len(pairings) == 1
        assert pairings[0]["participant1"] == "Club 38345 2"
        assert pairings[0]["participant2"] == "Club 38429 1"
        assert pairings[0]["score1"] == 0.0
        assert pairings[0]["score2"] == 6.0

    def test_parse_draw_scores(self, api_scraper):
        """Test parsing draw scores (0.5 - 0.5)."""
        round_data = [
            {
                "roundNr": 1,
                "board": 3,
                "homeId": 456647,
                "homeTeamNumber": -1,
                "awayId": 348774,
                "awayTeamNumber": -1,
                "homeResult": 0.5,
                "awayResult": 0.5,
            },
        ]

        with patch.object(api_scraper, "_resolve_player_name") as mock_player:
            mock_player.side_effect = lambda pid: f"Player {pid}"

            pairings = api_scraper.parse_round_pairings(json.dumps(round_data), 1)

        assert pairings[0]["score1"] == 0.5
        assert pairings[0]["score2"] == 0.5


# ============================================================================
# NAME RESOLUTION
# ============================================================================


class TestPlayerNameResolution:
    """Tests for player name lookup and caching."""

    def test_resolve_player_name_success(self, api_scraper):
        """Test successful player name lookup."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "firstName": "Nils",
            "lastName": "Åkervall",
        }

        with patch.object(api_scraper.session, "get", return_value=mock_response):
            name = api_scraper._resolve_player_name(348550)

        assert name == "Nils Åkervall"

    def test_resolve_player_name_failure(self, api_scraper):
        """Test fallback when player lookup fails."""
        mock_response = Mock()
        mock_response.status_code = 404

        with patch.object(api_scraper.session, "get", return_value=mock_response):
            name = api_scraper._resolve_player_name(999999)

        assert name == "Player 999999"

    def test_player_name_caching(self, api_scraper):
        """Test that player names are cached after first lookup."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "firstName": "Test",
            "lastName": "Player",
        }

        with patch.object(
            api_scraper.session, "get", return_value=mock_response
        ) as mock_get:
            # First call - should hit API
            api_scraper._resolve_player_name(12345)
            # Second call - should use cache
            api_scraper._resolve_player_name(12345)

            assert mock_get.call_count == 1

    def test_resolve_name_routes_to_player_for_individual(self, api_scraper):
        """Test that team_number == -1 routes to player lookup."""
        api_scraper._player_cache[100] = "Cached Player"

        name = api_scraper._resolve_name(100, -1)
        assert name == "Cached Player"

    def test_resolve_name_routes_to_club_for_team(self, api_scraper):
        """Test that team_number > 0 routes to club lookup."""
        api_scraper._club_cache[200] = "Cached Club"

        name = api_scraper._resolve_name(200, 1)
        assert name == "Cached Club 1"


class TestClubNameResolution:
    """Tests for club name lookup and caching."""

    def test_resolve_club_name_success(self, api_scraper):
        """Test successful club name lookup."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "SS Manhem"}

        with patch.object(api_scraper.session, "get", return_value=mock_response):
            name = api_scraper._resolve_club_name(38345, 2)

        assert name == "SS Manhem 2"

    def test_resolve_club_name_failure(self, api_scraper):
        """Test fallback when club lookup fails."""
        mock_response = Mock()
        mock_response.status_code = 404

        with patch.object(api_scraper.session, "get", return_value=mock_response):
            name = api_scraper._resolve_club_name(999999, 1)

        assert name == "Club 999999 1"

    def test_club_name_caching(self, api_scraper):
        """Test that club names are cached after first lookup."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "Lunds ASK"}

        with patch.object(
            api_scraper.session, "get", return_value=mock_response
        ) as mock_get:
            api_scraper._resolve_club_name(38429, 1)
            api_scraper._resolve_club_name(38429, 2)  # different team number

            # Should only hit API once (club name cached, team number appended)
            assert mock_get.call_count == 1


# ============================================================================
# FETCH ALL RESULTS
# ============================================================================


class TestFetchAllResults:
    """Tests for fetching all round results."""

    def test_fetch_individual_results(self, api_scraper):
        """Test fetching individual tournament results."""
        api_scraper._tournament_id = 17803

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"roundNr": 1, "board": 1, "homeId": 100, "awayId": 200},
        ]

        with patch.object(
            api_scraper.session, "get", return_value=mock_response
        ) as mock_get:
            results = api_scraper._fetch_all_results()

            assert len(results) == 1
            assert api_scraper._is_team_tournament is False
            # Should only call individual endpoint
            assert "tournamentresults/roundresults/id/17803" in mock_get.call_args[0][0]

    def test_fetch_team_results_fallback(self, api_scraper):
        """Test falling back to team endpoint when individual fails."""
        api_scraper._tournament_id = 17852

        mock_individual = Mock()
        mock_individual.status_code = 404

        mock_team = Mock()
        mock_team.status_code = 200
        mock_team.json.return_value = [
            {"roundNr": 1, "board": -1000, "homeId": 1, "awayId": 2},
        ]

        with patch.object(
            api_scraper.session, "get", side_effect=[mock_individual, mock_team]
        ) as mock_get:
            results = api_scraper._fetch_all_results()

            assert len(results) == 1
            assert api_scraper._is_team_tournament is True
            assert mock_get.call_count == 2

    def test_fetch_returns_empty_without_tournament_id(self, api_scraper):
        """Test that _fetch_all_results returns empty without tournament ID."""
        api_scraper._tournament_id = None
        results = api_scraper._fetch_all_results()
        assert results == []


# ============================================================================
# FULL WORKFLOW (fetch_all_rounds)
# ============================================================================


class TestFullWorkflow:
    """Integration tests for the full scraping workflow."""

    def test_fetch_all_rounds_individual(self, api_scraper):
        """Test full workflow for individual tournament."""
        mock_group = Mock()
        mock_group.status_code = 200
        mock_group.json.return_value = {"name": "Test Tournament"}
        mock_group.text = json.dumps({"name": "Test Tournament"})

        mock_results = Mock()
        mock_results.status_code = 200
        mock_results.json.return_value = [
            {"roundNr": 1, "board": 1, "homeId": 100, "awayId": 200},
            {"roundNr": 2, "board": 1, "homeId": 200, "awayId": 100},
        ]

        with patch.object(
            api_scraper.session, "get", side_effect=[mock_group, mock_results]
        ):
            name, rounds = api_scraper.fetch_all_rounds(
                "https://member.schack.se/ShowTournamentServlet?id=17803"
            )

        assert name == "Test Tournament"
        assert rounds == [1, 2]

    def test_fetch_all_rounds_team(self, api_scraper):
        """Test full workflow for team tournament."""
        mock_group = Mock()
        mock_group.status_code = 200
        mock_group.json.return_value = {"name": "Team Cup 2026"}
        mock_group.text = json.dumps({"name": "Team Cup 2026"})

        mock_individual = Mock()
        mock_individual.status_code = 404

        mock_team = Mock()
        mock_team.status_code = 200
        mock_team.json.return_value = [
            {"roundNr": 1, "board": -1000, "homeId": 1, "awayId": 2},
            {"roundNr": 2, "board": -1000, "homeId": 2, "awayId": 3},
            {"roundNr": 1, "board": -1000, "homeId": 3, "awayId": 4},
        ]

        with patch.object(
            api_scraper.session,
            "get",
            side_effect=[mock_group, mock_individual, mock_team],
        ):
            name, rounds = api_scraper.fetch_all_rounds(
                "https://member.schack.se/ShowTournamentServlet?id=17852"
            )

        assert name == "Team Cup 2026"
        assert rounds == [1, 2]

    def test_fetch_round_pairings_full_flow(self, api_scraper):
        """Test fetching and parsing pairings for a specific round."""
        api_scraper._all_results = [
            {
                "roundNr": 1,
                "board": 1,
                "homeId": 100,
                "homeTeamNumber": -1,
                "awayId": 200,
                "awayTeamNumber": -1,
                "homeResult": 1.0,
                "awayResult": 0.0,
            },
            {
                "roundNr": 2,
                "board": 1,
                "homeId": 200,
                "homeTeamNumber": -1,
                "awayId": 100,
                "awayTeamNumber": -1,
                "homeResult": 0.0,
                "awayResult": 1.0,
            },
        ]

        with patch.object(api_scraper, "_resolve_player_name") as mock_player:
            mock_player.side_effect = lambda pid: f"Player {pid}"

            round_json = api_scraper.fetch_round_url(
                "https://member.schack.se?id=123", 1
            )
            pairings = api_scraper.parse_round_pairings(round_json, 1)

        assert len(pairings) == 1
        assert pairings[0]["participant1"] == "Player 100"
        assert pairings[0]["participant2"] == "Player 200"
        assert pairings[0]["score1"] == 1.0
        assert pairings[0]["score2"] == 0.0


# ============================================================================
# BUILD PAIRING DICT
# ============================================================================


class TestBuildPairingDict:
    """Tests for the static _build_pairing_dict helper."""

    def test_build_pairing_dict_basic(self):
        """Test basic pairing dict construction."""
        result = SchackSeApiScraper._build_pairing_dict(
            team1="Alice",
            team2="Bob",
            board_number=1,
            score1=1.0,
            score2=0.0,
        )

        assert result == {
            "participant1": "Alice",
            "participant2": "Bob",
            "board_number": 1,
            "score1": 1.0,
            "score2": 0.0,
        }

    def test_build_pairing_dict_defaults(self):
        """Test pairing dict with default (None) values."""
        result = SchackSeApiScraper._build_pairing_dict(
            team1="Alice",
            team2="Bob",
        )

        assert result["board_number"] is None
        assert result["score1"] is None
        assert result["score2"] is None
