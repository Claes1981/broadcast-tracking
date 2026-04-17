"""
Pytest configuration and shared fixtures.
"""

import pytest
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Configure pytest
def pytest_addoption(parser):
    """Add custom pytest command-line options."""
    parser.addoption(
        "--no-gui",
        action="store_true",
        default=False,
        help="Skip GUI tests that require PyQt6",
    )

    # Add custom markers
    parser.addini("gui", "mark test as requiring GUI (PyQt6)")
    parser.addini("integration", "mark test as integration test")
    parser.addini("offline", "mark test as testing offline functionality")


def pytest_collection_modifyitems(config, items):
    """Modify test items based on configuration."""
    # Skip GUI tests if --no-gui is passed
    if config.getoption("--no-gui"):
        skip_gui = pytest.mark.skip(reason="GUI tests disabled")
        for item in items:
            if "gui" in item.keywords:
                item.add_marker(skip_gui)


# Shared fixtures can be added here
@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_data_dir(project_root):
    """Return a directory for test data."""
    test_dir = project_root / "tests" / "test_data"
    test_dir.mkdir(exist_ok=True)
    return test_dir
