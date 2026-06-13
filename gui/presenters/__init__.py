"""Presenters - separate business logic from GUI concerns."""
from gui.presenters.scraper_presenter import ScraperPresenter
from gui.presenters.manual_entry_presenter import ManualEntryPresenter

__all__ = ["ScraperPresenter", "ManualEntryPresenter"]
