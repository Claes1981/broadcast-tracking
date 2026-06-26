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
           └── gui/presenters/ (4 presenters, lazy-loaded via @property)
               ├── scraper_presenter.py      (fetch & import rounds)
               ├── manual_entry_presenter.py (offline round entry)
               ├── round_view_presenter.py   (round/participant display data)
               └── allocation_presenter.py   (digital board allocation)
           └── gui/pairing_card_builder.py   (pairing card widget construction)
           └── gui/dialogs.py                (7 dialog classes)
           └── gui/styles.py                 (QSS constants + style helpers)
database/ → SQLAlchemy ORM, SQLite files in tournament_data/
           ├── models.py       (Tournament, Participant, Round, Pairing, DigitalAssignment)
           ├── queries.py      (all DB queries — logic/presenters MUST use this layer)
           └── init_db.py      (create/open tournament, uses queries.py)
logic/ → allocator.py, tournament.py, pairing.py (dataclasses)
scrapers/ → base.py (ABC), schack_se.py (Swedish Chess Federation)
utils/ → export.py (Exporter strategy pattern: Csv/Json/Statistics)
config.py → DATA_DIR, DEFAULT_DIGITAL_BOARDS, DIGITAL_BOARD_PREFIX, UI dimensions
```

### Key Design Patterns

- **Presenter Pattern**: Business logic extracted from `MainWindow` into 4 presenters in `gui/presenters/`. Presenters receive `session`, `tournament_id`, and callbacks via constructor. `MainWindow` delegates to them.
- **Lazy Loading**: Presenters are created lazily via `@property` + `@setter` pattern. The `@setter` enables test mocking.
- **Strategy Pattern**: Export uses `Exporter` ABC with `CsvExporter`, `JsonExporter`, `StatisticsExporter`. Call `export(session, id, path, exporter_type)` dispatcher.
- **Query Layer**: ALL SQLAlchemy queries go through `database/queries.py`. Logic and presenter layers must NOT use `session.query()` directly.
- **Re-exports**: `database/__init__.py`, `logic/__init__.py`, `utils/__init__.py`, `gui/presenters/__init__.py` expose public APIs.

### Module Responsibilities

- `database/__init__.py` re-exports all query functions from `queries.py`
- `logic/__init__.py` re-exports allocator, tournament, and dataclass functions
- `logic/pairing.py` defines `PairingData`, `RoundData`, `TournamentData` dataclasses
- `gui/styles.py` defines QSS constants and `create_card_style_from_data` / `create_status_text_from_data` helpers
- Each tournament gets its own SQLite file in `tournament_data/`

## Code Style

- **PEP 8**: Follow standard Python style guidelines
- **Type hints**: All functions have type annotations
  - Use built-in `list[X]`, `tuple[X, Y]`, `X | None` (NOT `List`, `Tuple`, `Optional`)
  - `Callable` from `collections.abc` (NOT `typing`)
  - `Protocol` and `Final` remain in `typing` (correct location)
- **Docstrings**: All public functions/classes have docstrings describing purpose
- **Naming**: snake_case for functions/variables, CamelCase for classes
- **Imports**: Grouped by standard library, third-party, local imports
- **Inline imports**: Avoid — move to module level unless circular import risk

## Testing

- **Framework**: pytest with fixtures in `tests/conftest.py`
- **Structure**: One test file per module (`test_app.py`, `test_gui.py`, `test_manual_entry.py`)
- **Markers**: `--no-gui` flag skips GUI tests; `gui`, `integration`, `offline` markers
- **Fixtures**: `project_root` (session scope), `test_data_dir` (session scope)
- **Pattern**: Tests use `unittest.mock` for network/DB mocking
- **Mocking presenters**: Use `@setter` on lazy `@property` to inject mock presenters in tests

## GUI Conventions

- **Framework**: PyQt6 with standard widgets
- **Dialog helpers**: Use `_create_button_layout()` for Cancel/OK buttons, `_validate_non_empty()` for field validation
- **Tournament type selection**: Use `QComboBox` with "individual"/"team" options
- **Manual pairing dialog**: Uses `QComboBox(setEditable=True)` with sorted participant names; allows free-text entry
- **ManualPairingDialog**: Uses `_p1_combo`/`_p2_combo` (QComboBox), reads from `.currentText()`
- **ManualRoundDialog**: Accepts `participant_names: list[str] | None` parameter
- **PairingCardBuilder**: Constructs pairing card widgets from `PairingCardData` objects via callback Protocol

## Scraper Conventions

- **Multi-method parsing**: `parse_round_pairings` tries 3 methods in order
- **Method 1**: Individual tournament format (`greyproptable` with `listheader` cells)
  - Filter: Skip rows where `team2.startswith("E") and team2[1:].isdigit()` (Elo ratings)
- **Method 2**: Team tournament format with `HEMMALAG`/`BORTALAG` column headers
- **Method 3**: Headerless team tournament with fixed cell positions:
  - C4=home team, C6=home Elo, C8="-", C12=away team, C14=away Elo, C16=result
- **Fractional score parsing**: Replace "½" → ".5" (NOT "0.5") to avoid "3½" → "30.5"
- **Base class**: `BaseScraper` ABC defines interface + concrete workflow methods (`fetch_all_rounds`, `fetch_round_pairings`)

## Database Conventions

- **ORM**: SQLAlchemy with `declarative_base()` pattern
- **Models**: `Tournament`, `Participant`, `Round`, `Pairing`, `DigitalAssignment`
- **Relationships**: All use `back_populates` for bidirectional navigation
- **Cascade**: `cascade="all, delete-orphan"` on parent relationships
- **Constraints**: `UniqueConstraint` for tournament+participant, tournament+round
- **Participant type**: `'player'` or `'team'` string field
- **Digital assignment**: `uselist=False` for one-to-one pairing relationship
- **Queries**: `queries.py` functions return `.first()` → type hints use `X | None`
- **Datetime**: Use `datetime.now()` for defaults (NOT deprecated `datetime.utcnow()`)

## Key Conventions

- **Digital board labels**: "Board A", "Board B", etc. (letters, not numbers)
- **Fractional scores**: Parse "½" → ".5" (not "0.5") to avoid "3½" → "30.5"
- **Tournament types**: "individual" or "team"
- **Team pairings**: Scraper uses HEMMALAG (home) vs BORTALAG (away) columns
- **Re-exports**: `logic/__init__.py`, `database/__init__.py`, `utils/__init__.py` expose public API
- **Magic numbers**: Named constants in `config.py` (UI dimensions) and scraper classes

## Common Pitfalls

1. **Query layer only**: Logic and presenter layers must use `database/queries.py`, NOT `session.query()` directly
2. **Always check `if not self.session`** in GUI callbacks before DB operations
3. **Allocation edge case**: When boards ≥ pairings, assign labels to all pairings (don't return empty)
4. **ManualPairingDialog** uses `_p1_combo`/`_p2_combo` (QComboBox), not `_p1_edit`/`_p2_edit` (QLineEdit)
5. **ManualPairingDialog.get_data()** reads from `.currentText()`, not `.text()`
6. **Scraper Elo filter**: Team tournament match tables contain Elo ratings in `listheader` cells - filter with `team2.startswith("E") and team2[1:].isdigit()`
7. **Scraper Method 3**: Requires 17+ cells per row with separator "-" at C8
8. **`not Column[bool]` bug**: SQLAlchemy `Column[bool]` is always truthy — use `Column == False` instead
9. **session.flush() needed**: After `session.delete()` in allocator, flush before new INSERT to avoid UNIQUE constraint errors
10. **Presenter lazy loading**: Use `@setter` to mock presenters in tests that bypass `load_tournament`

## Data Flow

1. Create tournament → SQLite DB in `tournament_data/`
2. Fetch pairings (ScraperPresenter) OR manual entry (ManualEntryPresenter, offline mode)
3. Allocate digital boards (AllocationPresenter → logic/allocator.py)
4. Manual adjustments override allocation (preserved on re-allocation)
5. Export via strategy pattern (`export()` dispatcher → Csv/Json/StatisticsExporter)
