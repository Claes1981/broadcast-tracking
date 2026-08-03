"""Pytest configuration and shared fixtures."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup - run once at import so all test modules can import app packages
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Pytest hooks
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    """Add custom pytest command-line options."""
    parser.addoption(
        "--no-gui",
        action="store_true",
        default=False,
        help="Skip GUI tests that require PyQt6",
    )
    parser.addini("gui", "mark test as requiring GUI (PyQt6)")
    parser.addini("integration", "mark test as integration test")
    parser.addini("offline", "mark test as testing offline functionality")


def pytest_collection_modifyitems(config, items):
    """Skip GUI tests when --no-gui is passed."""
    if config.getoption("--no-gui"):
        skip_gui = pytest.mark.skip(reason="GUI tests disabled")
        for item in items:
            if "gui" in item.keywords:
                item.add_marker(skip_gui)


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def test_data_dir(project_root):
    """Return a directory for test data."""
    test_dir = project_root / "tests" / "test_data"
    test_dir.mkdir(exist_ok=True)
    return test_dir


# ---------------------------------------------------------------------------
# GUI fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def qt_app():
    """Create a QApplication for testing."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


# ---------------------------------------------------------------------------
# Instance-scoped database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_database_path():
    """Yield a factory that creates context managers mocking init_db.get_database_path.

    Each call creates a fresh temp directory. The temp dir is cleaned up on exit.

    Usage:
        def test_something(mock_database_path):
            with mock_database_path() as db_path:
                create_tournament("My Tournament")  # uses db_path
    """
    from contextlib import suppress
    from database import init_db

    original_get_path = init_db.get_database_path
    temp_dirs: list[str] = []

    class _MockPath:
        def __enter__(self):
            temp_dir = tempfile.mkdtemp()
            temp_dirs.append(temp_dir)
            init_db.get_database_path = lambda name: os.path.join(
                temp_dir, "test.sqlite"
            )
            return os.path.join(temp_dir, "test.sqlite")

        def __exit__(self, exc_type, exc_val, exc_tb):
            init_db.get_database_path = original_get_path

    def factory():
        return _MockPath()

    yield factory

    # Cleanup all temp directories after test
    for d in temp_dirs:
        with suppress(OSError):
            shutil.rmtree(d)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing.

    Yields the path to the SQLite file.  The database directory is
    automatically cleaned up after the test.
    """
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.sqlite")

    from database.init_db import create_database

    create_database("test")

    from database import init_db

    original_get_path = init_db.get_database_path
    call_counter = [0]

    def mock_get_path(name):
        call_counter[0] += 1
        if call_counter[0] == 1:
            return db_path
        return os.path.join(temp_dir, f"test_{call_counter[0]}.sqlite")

    init_db.get_database_path = mock_get_path
    yield db_path

    # Cleanup
    from contextlib import suppress

    with suppress(OSError):
        shutil.rmtree(temp_dir)
    init_db.get_database_path = original_get_path


@pytest.fixture
def temp_db_path(mock_database_path):
    """Yield a temporary database path string via mock_database_path."""
    with mock_database_path() as db_path:
        yield str(db_path)


@pytest.fixture
def tournament_session(temp_db):
    """Create a tournament and return ``(session, tournament_id, db_path)``."""
    from database.init_db import create_tournament, get_session

    db_path, tournament_id = create_tournament(
        name="Test Tournament",
        source_url="https://member.schack.se/test",
        tournament_type="individual",
    )
    session = get_session(db_path)
    yield session, tournament_id, db_path
    session.close()


@pytest.fixture
def tournament_with_rounds(temp_db):
    """Create a tournament with a round and pairings (Alice/Bob/Charlie).

    Returns ``(session, tournament_id, db_path)``.
    """
    from database.init_db import create_tournament, get_session
    from logic.pairing import PairingData, RoundData
    from logic.tournament import import_rounds_from_data

    db_path, tournament_id = create_tournament(
        name="Test Tournament",
        source_url="https://example.com",
        tournament_type="individual",
    )
    session = get_session(db_path)

    pairings = [
        PairingData(
            participant1_name="Alice", participant2_name="Bob", score1=1, score2=0
        ),
        PairingData(
            participant1_name="Charlie",
            participant2_name="David",
            score1=0.5,
            score2=0.5,
        ),
        PairingData(
            participant1_name="Eve", participant2_name="Frank", score1=0, score2=1
        ),
    ]
    round_data = RoundData(round_number=1, pairings=pairings)
    import_rounds_from_data(session, tournament_id, [round_data], "individual")
    session.commit()

    yield session, tournament_id, db_path
    session.close()
