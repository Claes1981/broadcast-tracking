"""Tests for ChessResultsScraper (Chess-Results.com HTML scraping).

Covers both individual and team tournament formats,
column layout detection, and edge cases.
"""

import pytest
from unittest.mock import Mock, patch

from scrapers.chess_results import ChessResultsScraper


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def scraper():
    """Create a fresh Chess-Results scraper instance."""
    return ChessResultsScraper()


# ============================================================================
# HTML TEMPLATES
# ============================================================================


def make_individual_table_wide(rows):
    """Build an HTML table in wide format (15 columns).

    Header: Bo.|No.| |WhTitle|White|Rtg|Pts|Result|Pts|BlTitle|Black|Rtg| |No|PGN
    """
    header = "<tr><td>Bo.</td><td>No.</td><td></td><td></td><td>White</td><td>Rtg</td><td>Pts.</td><td>Result</td><td>Pts.</td><td></td><td>Black</td><td>Rtg.</td><td></td><td>No.</td><td>PGN</td></tr>"
    row_html = "\n".join(rows)
    return f"<table>{header}\n{row_html}</table>"


def make_individual_table_narrow(rows):
    """Build an HTML table in narrow format (13 columns).

    Header: Bo.|No.|WhTitle|White|Rtg|Pts|Result|Pts|BlTitle|Black|Rtg|No|PGN
    """
    header = "<tr><td>Bo.</td><td>No.</td><td></td><td>White</td><td>Rtg</td><td>Pts.</td><td>Result</td><td>Pts.</td><td></td><td>Black</td><td>Rtg.</td><td>No.</td><td>PGN</td></tr>"
    row_html = "\n".join(rows)
    return f"<table>{header}\n{row_html}</table>"


def make_team_table(rows):
    """Build an HTML table in team format (6 columns).

    Header: No.|Team|Team|Res.|:|Res.
    """
    header = "<tr><td>No.</td><td>Team</td><td>Team</td><td>Res.</td><td>:</td><td>Res.</td></tr>"
    row_html = "\n".join(rows)
    return f"<table>{header}\n{row_html}</table>"


def wide_row(
    board, no1, w_title, white, rtg1, pts1, result, pts2, b_title, black, rtg2, no2
):
    """Build a data row for wide format (15 cells)."""
    return f"<tr><td>{board}</td><td>{no1}</td><td></td><td>{w_title}</td><td>{white}</td><td>{rtg1}</td><td>{pts1}</td><td>{result}</td><td>{pts2}</td><td>{b_title}</td><td>{black}</td><td>{rtg2}</td><td></td><td>{no2}</td><td>PGN</td></tr>"


def narrow_row(
    board, no1, w_title, white, rtg1, pts1, result, pts2, b_title, black, rtg2, no2
):
    """Build a data row for narrow format (13 cells)."""
    return f"<tr><td>{board}</td><td>{no1}</td><td>{w_title}</td><td>{white}</td><td>{rtg1}</td><td>{pts1}</td><td>{result}</td><td>{pts2}</td><td>{b_title}</td><td>{black}</td><td>{rtg2}</td><td>{no2}</td><td>PGN</td></tr>"


def team_row(match_no, home, away, h_res, a_res):
    """Build a data row for team format (6 cells)."""
    return f"<tr><td>{match_no}</td><td>{home}</td><td>{away}</td><td>{h_res}</td><td>:</td><td>{a_res}</td></tr>"


def make_page_with_table(table_html):
    """Wrap a table in a minimal page with other tables (simulating real page)."""
    return f"""<html><body>
<table><tr><td>Some other table</td></tr><tr><td>row2</td></tr></table>
<table><tr><td>Another table</td></tr><tr><td>row2</td></tr><tr><td>row3</td></tr></table>
{table_html}
</body></html>"""


def make_tournament_page(tournament_id, rounds, name_h2=None, name_title=None):
    """Build a tournament main page with round links."""
    h2 = f"<h2>{name_h2}</h2>" if name_h2 else ""
    title = (
        f"<title>Chess-Results Server Chess-results.com - {name_title}</title>"
        if name_title
        else ""
    )
    round_links = "\n".join(
        f'<a href="/tnr{tournament_id}.aspx?lan=1&amp;art=2&amp;rd={r}&amp;turdet=YES&amp;flag=30">Round {r}</a>'
        for r in rounds
    )
    return f"<html><head>{title}</head><body>{h2}<div>{round_links}</div></body></html>"


# ============================================================================
# TOURNAMENT ID EXTRACTION
# ============================================================================


class TestExtractTournamentId:
    """Tests for tournament ID extraction from URLs."""

    def test_extract_from_standard_url(self, scraper):
        tid = scraper._extract_tournament_id(
            "https://chess-results.com/tnr1277248.aspx?lan=1"
        )
        assert tid == 1277248

    def test_extract_from_subdomain_url(self, scraper):
        tid = scraper._extract_tournament_id(
            "https://s1.chess-results.com/tnr1440926.aspx?lan=1"
        )
        assert tid == 1440926

    def test_extract_from_round_url(self, scraper):
        tid = scraper._extract_tournament_id(
            "https://chess-results.com/tnr1430980.aspx?lan=1&art=2&rd=3"
        )
        assert tid == 1430980

    def test_returns_none_for_invalid_url(self, scraper):
        assert scraper._extract_tournament_id("https://example.com") is None
        assert scraper._extract_tournament_id("https://chess-results.com/") is None
        assert scraper._extract_tournament_id("") is None

    def test_fetch_tournament_url_raises_for_bad_url(self, scraper):
        with pytest.raises(ValueError, match="Could not extract tournament ID"):
            scraper.fetch_tournament_url("https://example.com")


# ============================================================================
# TOURNAMENT NAME PARSING
# ============================================================================


class TestParseTournamentName:
    """Tests for tournament name parsing from HTML."""

    def test_parse_from_h2_element(self, scraper):
        html = '<html><body><h2>9. Open Bohumín 2026 "A" - "Master"</h2></body></html>'
        name = scraper.parse_tournament_name(html)
        assert name == '9. Open Bohumín 2026 "A" - "Master"'

    def test_parse_from_title_when_no_h2(self, scraper):
        html = "<html><head><title>Chess-Results Server Chess-results.com - Belgian Open 2026</title></head><body></body></html>"
        name = scraper.parse_tournament_name(html)
        assert name == "Belgian Open 2026"

    def test_strips_chess_results_prefix(self, scraper):
        html = "<html><head><title>Chess-Results Server - Tournament Name</title></head><body></body></html>"
        name = scraper.parse_tournament_name(html)
        assert name == "Tournament Name"

    def test_fallback_to_unknown(self, scraper):
        html = "<html><body></body></html>"
        name = scraper.parse_tournament_name(html)
        assert name == "Unknown Tournament"

    def test_h2_takes_priority_over_title(self, scraper):
        html = "<html><head><title>Title Name</title></head><body><h2>H2 Name</h2></body></html>"
        name = scraper.parse_tournament_name(html)
        assert name == "H2 Name"

    def test_empty_h2_falls_back_to_title(self, scraper):
        html = (
            "<html><head><title>Title Name</title></head><body><h2></h2></body></html>"
        )
        name = scraper.parse_tournament_name(html)
        assert name == "Title Name"


# ============================================================================
# ROUND EXTRACTION
# ============================================================================


class TestParseRounds:
    """Tests for round number extraction from tournament page."""

    def test_extract_rounds_from_links(self, scraper):
        html = make_tournament_page(123, [1, 2, 3, 4, 5], name_h2="Test")
        rounds = scraper.parse_rounds(html)
        assert rounds == [1, 2, 3, 4, 5]

    def test_sorts_rounds(self, scraper):
        html = make_tournament_page(123, [5, 2, 8, 1, 3], name_h2="Test")
        rounds = scraper.parse_rounds(html)
        assert rounds == [1, 2, 3, 5, 8]

    def test_deduplicates_rounds(self, scraper):
        html = make_tournament_page(123, [1, 2, 2, 3, 1], name_h2="Test")
        rounds = scraper.parse_rounds(html)
        assert rounds == [1, 2, 3]

    def test_returns_empty_when_no_links(self, scraper):
        html = "<html><body>No links here</body></html>"
        rounds = scraper.parse_rounds(html)
        assert rounds == []

    def test_only_matches_art2_links(self, scraper):
        html = """<html><body>
<a href="/tnr123.aspx?lan=1&art=1&rd=1">Ranking R1</a>
<a href="/tnr123.aspx?lan=1&art=2&rd=3">Pairings R3</a>
<a href="/tnr123.aspx?lan=1&art=2&rd=1">Pairings R1</a>
</body></html>"""
        rounds = scraper.parse_rounds(html)
        assert rounds == [1, 3]


# ============================================================================
# FETCH ROUND URL
# ============================================================================


class TestFetchRoundUrl:
    """Tests for constructing and fetching round URLs."""

    def test_constructs_round_url(self, scraper):
        scraper._tournament_id = 1277248
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html>round data</html>"

        with patch.object(
            scraper.session, "get", return_value=mock_response
        ) as mock_get:
            result = scraper.fetch_round_url("https://chess-results.com/tnr1277248", 3)

            assert result == "<html>round data</html>"
            expected_url = (
                "https://chess-results.com/tnr1277248.aspx?"
                "lan=1&art=2&rd=3&turdet=YES&flag=30"
            )
            mock_get.assert_called_once_with(expected_url, timeout=30)

    def test_fallback_extract_id_from_base_url(self, scraper):
        """Test that fetch_round_url extracts tournament ID from base_url if not cached."""
        scraper._tournament_id = None
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html>round data</html>"

        with patch.object(scraper.session, "get", return_value=mock_response):
            result = scraper.fetch_round_url("https://chess-results.com/tnr999.aspx", 1)
            assert result == "<html>round data</html>"
            assert scraper._tournament_id == 999

    def test_raises_when_no_tournament_id(self, scraper):
        scraper._tournament_id = None
        with pytest.raises(ValueError, match="Could not extract tournament ID"):
            scraper.fetch_round_url("https://example.com", 1)


# ============================================================================
# PAIRINGS TABLE DETECTION
# ============================================================================


class TestFindPairingsTable:
    """Tests for finding the pairings table in HTML."""

    def test_find_individual_table_by_white_header(self, scraper):
        table = make_individual_table_wide(
            [
                wide_row(
                    "1",
                    "1",
                    "GM",
                    "Player1",
                    "2500",
                    "0",
                    "1 - 0",
                    "0",
                    "",
                    "Player2",
                    "2300",
                    "2",
                )
            ]
        )
        page = make_page_with_table(table)
        soup = scraper.__class__.__bases__[0].__new__(scraper.__class__)
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(page, "lxml")
        found = scraper._find_pairings_table(soup)
        assert found is not None
        assert "Player1" in found.get_text()

    def test_find_team_table_by_team_headers(self, scraper):
        table = make_team_table([team_row("1", "Team A", "Team B", "3", "1")])
        page = make_page_with_table(table)
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(page, "lxml")
        found = scraper._find_pairings_table(soup)
        assert found is not None
        assert "Team A" in found.get_text()

    def test_find_by_board_and_min_cells(self, scraper):
        """Test fallback detection via Bo. header + minimum cell count."""
        rows = []
        for i in range(13):
            rows.append(f"<td>cell{i}</td>")
        header_cells = "<td>Bo.</td>" + "".join(f"<td>h{i}</td>" for i in range(12))
        table = f"<table><tr>{header_cells}</tr><tr>{''.join(rows)}</tr></table>"
        page = make_page_with_table(table)
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(page, "lxml")
        found = scraper._find_pairings_table(soup)
        assert found is not None

    def test_fallback_to_last_large_table(self, scraper):
        """Test fallback to last table with enough rows."""
        page = """<html><body>
<table><tr><td>small</td></tr></table>
<table><tr><td>r1</td></tr><tr><td>r2</td></tr><tr><td>r3</td></tr></table>
</body></html>"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(page, "lxml")
        found = scraper._find_pairings_table(soup)
        assert found is not None

    def test_returns_none_for_empty_page(self, scraper):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<html><body></body></html>", "lxml")
        found = scraper._find_pairings_table(soup)
        assert found is None


# ============================================================================
# INDIVIDUAL TOURNAMENT - WIDE FORMAT (15 cols)
# ============================================================================


class TestIndividualWideFormat:
    """Tests for individual tournament parsing — wide format (Bohumín-style)."""

    def test_parse_wide_format_basic(self, scraper):
        """Test basic wide format with titles and names."""
        table = make_individual_table_wide(
            [
                wide_row(
                    "1",
                    "24",
                    "",
                    "Svoboda, Tobias",
                    "2036",
                    "0",
                    "0 - 1",
                    "0",
                    "IM",
                    "Pulpan, Jakub",
                    "2413",
                    "1",
                ),
                wide_row(
                    "2",
                    "2",
                    "GM",
                    "Andreev, Eduard",
                    "2397",
                    "0",
                    "1 - 0",
                    "0",
                    "",
                    "Fryc, Lukas",
                    "2032",
                    "25",
                ),
            ]
        )
        html = make_page_with_table(table)

        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 2

        # First pairing: no title for white, IM for black
        assert pairings[0]["participant1"] == "Svoboda, Tobias"
        assert pairings[0]["participant2"] == "IM Pulpan, Jakub"
        assert pairings[0]["board_number"] == 1
        assert pairings[0]["score1"] == 0.0
        assert pairings[0]["score2"] == 1.0

        # Second pairing: GM for white, no title for black
        assert pairings[1]["participant1"] == "GM Andreev, Eduard"
        assert pairings[1]["participant2"] == "Fryc, Lukas"
        assert pairings[1]["board_number"] == 2
        assert pairings[1]["score1"] == 1.0
        assert pairings[1]["score2"] == 0.0

    def test_parse_wide_format_draw(self, scraper):
        """Test draw result parsing."""
        table = make_individual_table_wide(
            [
                wide_row(
                    "3",
                    "10",
                    "FM",
                    "Player1",
                    "2200",
                    "1",
                    "½ - ½",
                    "1",
                    "WGM",
                    "Player2",
                    "2100",
                    "11",
                ),
            ]
        )
        html = make_page_with_table(table)

        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1
        assert pairings[0]["participant1"] == "FM Player1"
        assert pairings[0]["participant2"] == "WGM Player2"
        assert pairings[0]["score1"] == 0.5
        assert pairings[0]["score2"] == 0.5

    def test_parse_wide_format_skips_not_paired(self, scraper):
        """Test that not-paired rows are skipped."""
        table = make_individual_table_wide(
            [
                wide_row(
                    "1",
                    "1",
                    "",
                    "Paired1",
                    "2000",
                    "0",
                    "1 - 0",
                    "0",
                    "",
                    "Paired2",
                    "2000",
                    "2",
                ),
                # not-paired row (14 cells — missing last cell)
                "<tr><td>23</td><td>15</td><td></td><td></td><td>Posluszny, Tomasz</td><td>2102</td><td>0</td><td>0</td><td>0</td><td></td><td>not paired</td><td></td><td></td><td></td></tr>",
            ]
        )
        html = make_page_with_table(table)

        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1
        assert pairings[0]["participant1"] == "Paired1"

    def test_sets_is_team_tournament_false(self, scraper):
        """Test that _is_team_tournament is set to False for individual."""
        table = make_individual_table_wide(
            [
                wide_row(
                    "1",
                    "1",
                    "",
                    "White",
                    "2000",
                    "0",
                    "1 - 0",
                    "0",
                    "",
                    "Black",
                    "2000",
                    "2",
                ),
            ]
        )
        html = make_page_with_table(table)

        scraper.parse_round_pairings(html, 1)
        assert scraper._is_team_tournament is False


# ============================================================================
# INDIVIDUAL TOURNAMENT - NARROW FORMAT (13 cols)
# ============================================================================


class TestIndividualNarrowFormat:
    """Tests for individual tournament parsing — narrow format (Belgian Open-style)."""

    def test_parse_narrow_format_basic(self, scraper):
        """Test basic narrow format with titles and names."""
        table = make_individual_table_narrow(
            [
                narrow_row(
                    "1",
                    "1",
                    "FM",
                    "Nemegeer, Arne",
                    "2292",
                    "0",
                    "1 - 0",
                    "0",
                    "",
                    "Daems, Thibaut",
                    "1848",
                    "64",
                ),
                narrow_row(
                    "2",
                    "3",
                    "",
                    "Player1",
                    "2100",
                    "0",
                    "0 - 1",
                    "0",
                    "CM",
                    "Player2",
                    "2050",
                    "62",
                ),
            ]
        )
        html = make_page_with_table(table)

        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 2

        assert pairings[0]["participant1"] == "FM Nemegeer, Arne"
        assert pairings[0]["participant2"] == "Daems, Thibaut"
        assert pairings[0]["score1"] == 1.0
        assert pairings[0]["score2"] == 0.0

        assert pairings[1]["participant1"] == "Player1"
        assert pairings[1]["participant2"] == "CM Player2"

    def test_parse_narrow_format_both_titles(self, scraper):
        """Test narrow format with both players having titles."""
        table = make_individual_table_narrow(
            [
                narrow_row(
                    "1",
                    "5",
                    "GM",
                    "Karpov, Anatoly",
                    "2600",
                    "0",
                    "½ - ½",
                    "0",
                    "GM",
                    "Kasparov, Garry",
                    "2700",
                    "1",
                ),
            ]
        )
        html = make_page_with_table(table)

        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1
        assert pairings[0]["participant1"] == "GM Karpov, Anatoly"
        assert pairings[0]["participant2"] == "GM Kasparov, Garry"
        assert pairings[0]["score1"] == 0.5
        assert pairings[0]["score2"] == 0.5


# ============================================================================
# COLUMN LAYOUT DETECTION
# ============================================================================


class TestDetectIndividualLayout:
    """Tests for header-based column layout detection."""

    def test_detect_wide_layout(self, scraper):
        """Test detection of wide format (15 cols)."""
        table_html = make_individual_table_wide([])
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(table_html, "lxml")
        table = soup.find("table")
        layout = scraper._detect_individual_layout(table)
        # Wide: White at idx 4, so title=3, name=4, result=7, black_title=9
        assert layout == (3, 4, 7, 9)

    def test_detect_narrow_layout(self, scraper):
        """Test detection of narrow format (13 cols)."""
        table_html = make_individual_table_narrow([])
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(table_html, "lxml")
        table = soup.find("table")
        layout = scraper._detect_individual_layout(table)
        # Narrow: White at idx 3, so title=2, name=3, result=6, black_title=8
        assert layout == (2, 3, 6, 8)

    def test_fallback_when_no_white_header(self, scraper):
        """Test fallback when White/Black headers are missing."""
        table_html = "<table><tr><td>Bo.</td><td>No.</td><td>Name</td></tr></table>"
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(table_html, "lxml")
        table = soup.find("table")
        layout = scraper._detect_individual_layout(table)
        assert layout == (2, 3, 6, 8)  # fallback to narrow

    def test_fallback_for_empty_table(self, scraper):
        """Test fallback for table with no rows."""
        table_html = "<table></table>"
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(table_html, "lxml")
        table = soup.find("table")
        layout = scraper._detect_individual_layout(table)
        assert layout == (2, 3, 6, 8)


# ============================================================================
# TEAM TOURNAMENT
# ============================================================================


class TestTeamTournament:
    """Tests for team tournament pairings parsing."""

    def test_parse_team_pairings_basic(self, scraper):
        """Test basic team pairings parsing."""
        table = make_team_table(
            [
                team_row("1", "Team A", "Team B", "3", "1"),
                team_row("2", "Team C", "Team D", "2", "2"),
            ]
        )
        html = make_page_with_table(table)

        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 2

        assert pairings[0]["participant1"] == "Team A"
        assert pairings[0]["participant2"] == "Team B"
        assert pairings[0]["score1"] == 3.0
        assert pairings[0]["score2"] == 1.0

        assert pairings[1]["participant1"] == "Team C"
        assert pairings[1]["participant2"] == "Team D"
        assert pairings[1]["score1"] == 2.0
        assert pairings[1]["score2"] == 2.0

    def test_parse_team_pairings_with_half_scores(self, scraper):
        """Test team pairings with fractional scores."""
        table = make_team_table(
            [
                team_row("1", "Home Team", "Away Team", "2½", "1½"),
            ]
        )
        html = make_page_with_table(table)

        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1
        assert pairings[0]["score1"] == 2.5
        assert pairings[0]["score2"] == 1.5

    def test_sets_is_team_tournament_true(self, scraper):
        """Test that _is_team_tournament is set to True for team format."""
        table = make_team_table(
            [
                team_row("1", "Home", "Away", "4", "0"),
            ]
        )
        html = make_page_with_table(table)

        scraper.parse_round_pairings(html, 1)
        assert scraper._is_team_tournament is True

    def test_skip_empty_team_names(self, scraper):
        """Test that rows with empty team names are skipped."""
        table = make_team_table(
            [
                team_row("1", "Team A", "Team B", "3", "1"),
                team_row("2", "", "Team D", "0", "4"),
                team_row("3", "Team E", "", "2", "2"),
            ]
        )
        html = make_page_with_table(table)

        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1
        assert pairings[0]["participant1"] == "Team A"


# ============================================================================
# RESULT PARSING
# ============================================================================


class TestParseIndividualResult:
    """Tests for individual result parsing."""

    def test_win_for_white(self, scraper):
        s1, s2 = scraper._parse_individual_result("1")
        assert s1 == 1.0 and s2 == 0.0

    def test_win_for_black(self, scraper):
        s1, s2 = scraper._parse_individual_result("0")
        assert s1 == 0.0 and s2 == 1.0

    def test_draw_half_unicode(self, scraper):
        s1, s2 = scraper._parse_individual_result("½")
        assert s1 == 0.5 and s2 == 0.5

    def test_third_point(self, scraper):
        s1, s2 = scraper._parse_individual_result("⅓")
        assert s1 == 0.33 and s2 == 0.67

    def test_two_thirds(self, scraper):
        s1, s2 = scraper._parse_individual_result("⅔")
        assert s1 == 0.67 and s2 == 0.33

    def test_unfinished(self, scraper):
        s1, s2 = scraper._parse_individual_result("-")
        assert s1 is None and s2 is None

    def test_empty_string(self, scraper):
        s1, s2 = scraper._parse_individual_result("")
        assert s1 is None and s2 is None

    def test_invalid_text(self, scraper):
        s1, s2 = scraper._parse_individual_result("invalid")
        assert s1 is None and s2 is None


class TestParseTeamResult:
    """Tests for team result parsing."""

    def test_normal_scores(self, scraper):
        s1, s2 = scraper._parse_team_result("3", "1")
        assert s1 == 3.0 and s2 == 1.0

    def test_half_scores(self, scraper):
        s1, s2 = scraper._parse_team_result("2½", "1½")
        assert s1 == 2.5 and s2 == 1.5

    def test_empty_scores(self, scraper):
        s1, s2 = scraper._parse_team_result("", "")
        assert s1 is None and s2 is None

    def test_one_empty(self, scraper):
        s1, s2 = scraper._parse_team_result("3", "")
        assert s1 == 3.0 and s2 is None

    def test_invalid_text(self, scraper):
        s1, s2 = scraper._parse_team_result("abc", "xyz")
        assert s1 is None and s2 is None


# ============================================================================
# BOARD NUMBER PARSING
# ============================================================================


class TestParseBoardNumber:
    """Tests for board number parsing."""

    def test_valid_number(self, scraper):
        assert scraper._parse_board_number("5") == 5

    def test_zero(self, scraper):
        assert scraper._parse_board_number("0") == 0

    def test_invalid_text(self, scraper):
        assert scraper._parse_board_number("Bo.") is None

    def test_empty_string(self, scraper):
        assert scraper._parse_board_number("") is None


# ============================================================================
# BUILD PAIRING DICT
# ============================================================================


class TestBuildPairingDict:
    """Tests for the static _build_pairing_dict helper."""

    def test_full_pairing(self, scraper):
        result = scraper._build_pairing_dict(
            team1="Alice",
            team2="Bob",
            board_number=3,
            score1=1.0,
            score2=0.0,
        )
        assert result == {
            "participant1": "Alice",
            "participant2": "Bob",
            "board_number": 3,
            "score1": 1.0,
            "score2": 0.0,
        }

    def test_defaults(self, scraper):
        result = scraper._build_pairing_dict(team1="X", team2="Y")
        assert result["board_number"] is None
        assert result["score1"] is None
        assert result["score2"] is None


# ============================================================================
# PARSE ROUND PAIRINGS EDGE CASES
# ============================================================================


class TestParseRoundPairingsEdgeCases:
    """Edge cases for parse_round_pairings."""

    def test_empty_html(self, scraper):
        pairings = scraper.parse_round_pairings("", 1)
        assert pairings == []

    def test_no_pairings_table(self, scraper):
        html = "<html><body><p>No tables here</p></body></html>"
        pairings = scraper.parse_round_pairings(html, 1)
        assert pairings == []

    def test_table_with_only_header(self, scraper):
        html = make_page_with_table(make_individual_table_wide([]))
        pairings = scraper.parse_round_pairings(html, 1)
        assert pairings == []

    def test_skips_header_row(self, scraper):
        """Test that the header row (Bo./No.) is not parsed as a pairing."""
        table = make_individual_table_wide(
            [
                wide_row(
                    "1",
                    "1",
                    "",
                    "White",
                    "2000",
                    "0",
                    "1 - 0",
                    "0",
                    "",
                    "Black",
                    "2000",
                    "2",
                ),
            ]
        )
        html = make_page_with_table(table)

        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1
        assert pairings[0]["participant1"] == "White"

    def test_skips_rows_with_too_few_cells(self, scraper):
        """Test that short rows are skipped."""
        table = make_individual_table_wide(
            [
                wide_row(
                    "1",
                    "1",
                    "",
                    "White",
                    "2000",
                    "0",
                    "1 - 0",
                    "0",
                    "",
                    "Black",
                    "2000",
                    "2",
                ),
                "<tr><td>short</td><td>row</td></tr>",
            ]
        )
        html = make_page_with_table(table)

        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1

    def test_empty_white_name_skipped(self, scraper):
        """Test that rows with empty white name are skipped."""
        table = make_individual_table_wide(
            [
                wide_row(
                    "1",
                    "1",
                    "",
                    "",
                    "2000",
                    "0",
                    "1 - 0",
                    "0",
                    "",
                    "Black",
                    "2000",
                    "2",
                ),
            ]
        )
        html = make_page_with_table(table)

        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 0

    def test_format_detection_prefers_individual(self, scraper):
        """Test that rows with >= INDIVIDUAL_MIN_CELLS are treated as individual."""
        # A row with 13+ cells is always treated as individual
        table = make_individual_table_narrow(
            [
                narrow_row(
                    "1",
                    "1",
                    "",
                    "White",
                    "2000",
                    "0",
                    "1 - 0",
                    "0",
                    "",
                    "Black",
                    "2000",
                    "2",
                ),
            ]
        )
        html = make_page_with_table(table)

        pairings = scraper.parse_round_pairings(html, 1)
        assert len(pairings) == 1
        assert scraper._is_team_tournament is False


# ============================================================================
# FETCH TOURNAMENT URL
# ============================================================================


class TestFetchTournamentUrl:
    """Tests for fetch_tournament_url."""

    def test_fetches_and_caches_id(self, scraper):
        url = "https://chess-results.com/tnr123456.aspx"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html>page</html>"

        with patch.object(scraper.session, "get", return_value=mock_response):
            result = scraper.fetch_tournament_url(url)

            assert result == "<html>page</html>"
            assert scraper._tournament_id == 123456

    def test_raises_on_http_error(self, scraper):
        import requests as req_lib

        url = "https://chess-results.com/tnr123456.aspx"
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = req_lib.HTTPError("404")

        with patch.object(scraper.session, "get", return_value=mock_response):
            with pytest.raises(req_lib.HTTPError):
                scraper.fetch_tournament_url(url)


# ============================================================================
# FULL WORKFLOW
# ============================================================================


class TestFullWorkflow:
    """Integration tests for the full scraping workflow."""

    def test_fetch_all_rounds_individual(self, scraper):
        """Test full workflow for individual tournament."""
        tournament_page = make_tournament_page(
            1277248, [1, 2, 3], name_h2="9. Open Bohumín 2026"
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = tournament_page

        with patch.object(scraper.session, "get", return_value=mock_response):
            name, rounds = scraper.fetch_all_rounds(
                "https://chess-results.com/tnr1277248.aspx?lan=1"
            )

        assert name == "9. Open Bohumín 2026"
        assert rounds == [1, 2, 3]
        assert scraper._tournament_id == 1277248

    def test_fetch_all_rounds_team(self, scraper):
        """Test full workflow for team tournament."""
        tournament_page = make_tournament_page(
            1430980,
            [1, 2, 3, 4, 5, 6, 7],
            name_title="BSV Berliner Schnellschach-MM 2026",
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = tournament_page

        with patch.object(scraper.session, "get", return_value=mock_response):
            name, rounds = scraper.fetch_all_rounds(
                "https://chess-results.com/tnr1430980.aspx?lan=1"
            )

        assert name == "BSV Berliner Schnellschach-MM 2026"
        assert rounds == [1, 2, 3, 4, 5, 6, 7]

    def test_fetch_round_pairings_workflow(self, scraper):
        """Test fetch_round_pairings default workflow method."""
        scraper._tournament_id = 1277248

        table = make_individual_table_wide(
            [
                wide_row(
                    "1",
                    "1",
                    "GM",
                    "White",
                    "2500",
                    "0",
                    "1 - 0",
                    "0",
                    "IM",
                    "Black",
                    "2400",
                    "2",
                ),
            ]
        )
        round_page = make_page_with_table(table)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = round_page

        with patch.object(scraper.session, "get", return_value=mock_response):
            pairings = scraper.fetch_round_pairings(
                "https://chess-results.com/tnr1277248.aspx", 1
            )

        assert len(pairings) == 1
        assert pairings[0]["participant1"] == "GM White"
        assert pairings[0]["participant2"] == "IM Black"

    def test_user_agent_is_set(self, scraper):
        """Test that the scraper sets the honest User-Agent."""
        from config import SCRAPER_USER_AGENT

        assert scraper.session.headers["User-Agent"] == SCRAPER_USER_AGENT


# ============================================================================
# BASE SCRAPER DEFAULT WORKFLOW METHODS
# ============================================================================


class TestBaseScraperDefaultWorkflows:
    """Tests for BaseScraper default workflow methods via ChessResultsScraper."""

    def test_fetch_all_rounds_calls_primitives(self, scraper):
        """Test that fetch_all_rounds calls fetch_tournament_url, parse_tournament_name, parse_rounds."""
        tournament_page = make_tournament_page(999, [1, 2], name_h2="Test")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = tournament_page

        with patch.object(scraper.session, "get", return_value=mock_response):
            name, rounds = scraper.fetch_all_rounds(
                "https://chess-results.com/tnr999.aspx"
            )

        assert name == "Test"
        assert rounds == [1, 2]

    def test_fetch_round_pairings_calls_primitives(self, scraper):
        """Test that fetch_round_pairings calls fetch_round_url then parse_round_pairings."""
        scraper._tournament_id = 999

        table = make_team_table(
            [
                team_row("1", "Home", "Away", "3", "1"),
            ]
        )
        round_page = make_page_with_table(table)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = round_page

        with patch.object(scraper.session, "get", return_value=mock_response):
            pairings = scraper.fetch_round_pairings(
                "https://chess-results.com/tnr999.aspx", 1
            )

        assert len(pairings) == 1
        assert pairings[0]["participant1"] == "Home"
        assert pairings[0]["participant2"] == "Away"
