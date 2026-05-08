# Broadcast Board Tracker - Agent Instructions

## Quick Start

```bash
python main.py                          # Run app
python -m pytest tests/ -v              # Run all tests
python -m pytest tests/ -v -k "allocation"  # Filter by keyword
```

GUI tests need `pytest-qt` and a display server. Use `-k "not gui"` to skip them.

## Architecture

```
main.py → gui/main_window.py (PyQt6 app)
database/ → SQLAlchemy ORM, SQLite files in tournament_data/
logic/ → allocator.py, tournament.py, pairing.py (dataclasses)
scrapers/ → schack_se.py (fetches from member.schack.se)
config.py → DATA_DIR, DEFAULT_DIGITAL_BOARDS, DIGITAL_BOARD_PREFIX
```

- `database/__init__.py` and `logic/__init__.py` re-export all public functions
- `logic/pairing.py` defines `PairingData`, `RoundData`, `TournamentData` dataclasses
- Each tournament gets its own SQLite file in `tournament_data/`

## Code Style

- **PEP 8**: Follow standard Python style guidelines
- **Type hints**: All functions have type annotations (use `typing` module)
- **Docstrings**: All public functions/classes have docstrings describing purpose
- **Naming**: snake_case for functions/variables, CamelCase for classes
- **Imports**: Grouped by standard library, third-party, local imports

## Testing

- **Framework**: pytest with fixtures in `tests/conftest.py`
- **Structure**: One test file per module (`test_app.py`, `test_gui.py`, `test_manual_entry.py`)
- **Markers**: `--no-gui` flag skips GUI tests; `gui`, `integration`, `offline` markers
- **Fixtures**: `project_root` (session scope), `test_data_dir` (session scope)
- **Pattern**: Tests use `unittest.mock` for network/DB mocking

## GUI Conventions

- **Framework**: PyQt6 with standard widgets
- **Dialog helpers**: Use `_create_button_layout()` for Cancel/OK buttons, `_validate_non_empty()` for field validation
- **Tournament type selection**: Use `QComboBox` with "individual"/"team" options
- **Manual pairing dialog**: Uses `QComboBox(setEditable=True)` with sorted participant names; allows free-text entry
- **ManualPairingDialog**: Uses `_p1_combo`/`_p2_combo` (QComboBox), reads from `.currentText()`
- **ManualRoundDialog**: Accepts `participant_names: list[str] | None` parameter

## Scraper Conventions

- **Multi-method parsing**: `parse_round_pairings` tries 3 methods in order
- **Method 1**: Individual tournament format (`greyproptable` with `listheader` cells)
  - Filter: Skip rows where `team2.startswith("E") and team2[1:].isdigit()` (Elo ratings)
- **Method 2**: Team tournament format with `HEMMALAG`/`BORTALAG` column headers
- **Method 3**: Headerless team tournament with fixed cell positions:
  - C4=home team, C6=home Elo, C8="-", C12=away team, C14=away Elo, C16=result
- **Fractional score parsing**: Replace "½" → ".5" (NOT "0.5") to avoid "3½" → "30.5"
- **Base class**: `BaseScraper` ABC defines interface for all scrapers

## Database Conventions

- **ORM**: SQLAlchemy with `declarative_base()` pattern
- **Models**: `Tournament`, `Participant`, `Round`, `Pairing`, `DigitalAssignment`
- **Relationships**: All use `back_populates` for bidirectional navigation
- **Cascade**: `cascade="all, delete-orphan"` on parent relationships
- **Constraints**: `UniqueConstraint` for tournament+participant, tournament+round
- **Participant type**: `'player'` or `'team'` string field
- **Digital assignment**: `uselist=False` for one-to-one pairing relationship

## Key Conventions

- **Digital board labels**: "Board A", "Board B", etc. (letters, not numbers)
- **Fractional scores**: Parse "½" → ".5" (not "0.5") to avoid "3½" → "30.5"
- **Tournament types**: "individual" or "team"
- **Team pairings**: Scraper uses HEMMALAG (home) vs BORTALAG (away) columns
- **Re-exports**: `logic/__init__.py` and `database/__init__.py` expose public API

## Common Pitfalls

1. **Tournament model needs `participants` relationship** with `back_populates` for ORM navigation
2. **Always check `if not self.session`** in GUI callbacks before DB operations
3. **Allocation edge case**: When boards ≥ pairings, assign labels to all pairings (don't return empty)
4. **ManualPairingDialog** uses `_p1_combo`/`_p2_combo` (QComboBox), not `_p1_edit`/`_p2_edit` (QLineEdit)
5. **ManualPairingDialog.get_data()** reads from `.currentText()`, not `.text()`
6. **Scraper Elo filter**: Team tournament match tables contain Elo ratings in `listheader` cells - filter with `team2.startswith("E") and team2[1:].isdigit()`
7. **Scraper Method 3**: Requires 17+ cells per row with separator "-" at C8

## Data Flow

1. Create tournament → SQLite DB in `tournament_data/`
2. Fetch pairings (scraper) OR manual entry (offline mode)
3. Allocate digital boards (minimizes combined digital round count)
4. Manual adjustments override allocation (preserved on re-allocation)
5. Export to CSV/JSON/statistics
