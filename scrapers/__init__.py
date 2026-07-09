from scrapers.base import BaseScraper
from scrapers.chess_results import ChessResultsScraper
from scrapers.schack_se import SchackSeScraper
from scrapers.schack_se_api import SchackSeApiScraper

__all__ = [
    "BaseScraper",
    "SchackSeScraper",
    "SchackSeApiScraper",
    "ChessResultsScraper",
]
