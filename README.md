# Broadcast Board Tracker

A GUI application for tracking digital board usage in chess tournaments. Automatically assigns digital boards to pairings based on participants' digital round history, with support for manual adjustments.

## Features

- **Automatic Digital Board Allocation**: Assigns digital boards to pairings with the least combined digital round history
- **Smart Algorithm**: Uses sum of both participants' digital round counts with random tie-breaking
- **Manual Adjustments**: Override automatic assignments, exclude pairings from digital boards
- **Swedish Chess Federation Integration**: Fetch pairings directly from member.schack.se
- **Offline Mode**: Manual data entry when scraper is unavailable
- **Export Statistics**: Generate CSV, JSON, and statistics reports
- **Color-Coded GUI**: Visual indicators for assigned (green), manual (yellow), excluded (red), and unassigned (gray) pairings
- **Persistent Storage**: SQLite databases with collision handling for filenames
- **Team & Individual Support**: Works with both team and individual tournaments

## Installation

### Requirements

- Python 3.11+
- PyQt6
- SQLAlchemy
- requests
- beautifulsoup4
- lxml
- pytest (for testing)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd broadcast-tracking
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python main.py
```

## Usage

### Creating a Tournament

1. Click "New Tournament" in the menu
2. Enter tournament name (required)
3. Enter source URL from member.schack.se (optional, for offline mode leave blank)
4. Select tournament type (individual or team)

### Fetching Pairings

1. Click "Fetch Pairings" in the menu
2. Enter the tournament URL (e.g., `https://member.schack.se/ShowTournamentServlet?id=12345`)
3. Select which rounds to import
4. Click "Fetch" to download pairings

### Allocating Digital Boards

1. Select the round from the dropdown
2. Set the number of digital boards available (default: 5)
3. Click "Allocate Boards" to automatically assign boards
4. Boards are labeled "Board A", "Board B", etc.

### Manual Adjustments

- **Assign Board**: Right-click a pairing and select "Assign Digital Board"
- **Remove Assignment**: Right-click an assigned pairing and select "Remove Assignment"
- **Exclude from Digital**: Right-click a pairing and select "Exclude from Digital Boards"
- **Clear All**: Click "Clear Assignments" to remove all assignments for the current round

### Correcting Previous Rounds

1. Navigate to the round using the dropdown or Previous/Next buttons
2. Make manual adjustments as needed
3. Re-run allocation if desired (respects manual assignments)

### Exporting Data

1. Click "Export" in the menu
2. Choose format: CSV, JSON, or Statistics
3. Select destination file
4. Click "Save"

## Database

Databases are stored in `tournament_data/` directory with filenames based on tournament names. Collision handling appends `_1`, `_2`, etc. for duplicate names.

## Testing

Run the test suite:
```bash
python -m pytest tests/ -v
```

Or use the test runner:
```bash
python run_tests.py
```

## Project Structure

```
broadcast-tracking/
├── main.py                 # Application entry point
├── config.py               # Configuration constants
├── database/
│   ├── models.py           # SQLAlchemy ORM models
│   ├── init_db.py          # Database initialization
│   └── queries.py          # Database query helpers
├── gui/
│   ├── main_window.py      # Main application window
│   ├── dialogs.py          # Dialog classes
│   └── styles.py           # Qt stylesheet constants
├── logic/
│   ├── allocator.py        # Digital board allocation algorithm
│   ├── pairing.py          # Pairing data structures
│   └── tournament.py       # Tournament management logic
├── scrapers/
│   ├── base.py             # Abstract scraper base class
│   └── schack_se.py        # Swedish Chess Federation scraper
├── utils/
│   └── export.py           # Export functions (CSV, JSON, stats)
├── tests/
│   ├── test_app.py         # Unit and integration tests
│   ├── test_gui.py         # GUI tests
│   └── conftest.py         # Pytest configuration
└── tournament_data/        # SQLite database storage
```

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please ensure all tests pass before submitting changes.
