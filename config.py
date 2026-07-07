import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "tournament_data")
os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_DIGITAL_BOARDS = 5
DIGITAL_BOARD_PREFIX = "Board"

# Scraper identity
SCRAPER_USER_AGENT = (
    "broadcast-tracking/1.0 (<https://github.com/Claes1981/broadcast-tracking>)"
)

# UI Dimensions
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800
LEFT_PANEL_WIDTH = 400
RIGHT_PANEL_WIDTH = 800
