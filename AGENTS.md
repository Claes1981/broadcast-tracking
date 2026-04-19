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

## Key Conventions

- **Digital board labels**: "Board A", "Board B", etc. (letters, not numbers)
- **Fractional scores**: Parse "½" → ".5" (not "0.5") to avoid "3½" → "30.5"
- **Tournament types**: "individual" or "team"
- **Team pairings**: Scraper uses HEMMALAG (home) vs BORTALAG (away) columns
- **Manual pairing dialog**: Uses `QComboBox(setEditable=True)` with sorted participant names; still allows free-text entry
- **ManualRoundDialog** accepts `participant_names: list[str] | None` parameter

## Common Pitfalls

1. **Tournament model needs `participants` relationship** with `back_populates` for ORM navigation
2. **Always check `if not self.session`** in GUI callbacks before DB operations
3. **Allocation edge case**: When boards ≥ pairings, assign labels to all pairings (don't return empty)
4. **ManualPairingDialog** uses `_p1_combo`/`_p2_combo` (QComboBox), not `_p1_edit`/`_p2_edit` (QLineEdit)
5. **ManualPairingDialog.get_data()** reads from `.currentText()`, not `.text()`

## Data Flow

1. Create tournament → SQLite DB in `tournament_data/`
2. Fetch pairings (scraper) OR manual entry (offline mode)
3. Allocate digital boards (minimizes combined digital round count)
4. Manual adjustments override allocation (preserved on re-allocation)
5. Export to CSV/JSON/statistics
