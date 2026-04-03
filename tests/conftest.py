import sqlite3
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from backend.DataFetcher import DataFetcher
from backend.config import AppConfig


@pytest.fixture
def sample_html_path():
    return Path(__file__).parent / "fixtures" / "sample_listings.html"


@pytest.fixture
def populated_db_path(tmp_path, sample_html_path):
    db_path = tmp_path / "test_data.db"
    fetcher = DataFetcher(
        source=str(sample_html_path),
        db_path=str(db_path),
        config=AppConfig(db_path=db_path, remote_geocoding_enabled=False),
    )
    fetcher.refresh_database(reset=True)
    return db_path


@pytest.fixture
def demo_db_path(tmp_path):
    db_path = tmp_path / "demo_data.db"
    fetcher = DataFetcher(
        source="test://default",
        db_path=str(db_path),
        config=AppConfig(db_path=db_path, remote_geocoding_enabled=False),
    )
    fetcher.refresh_database(reset=True)
    return db_path


@pytest.fixture
def empty_db_path(tmp_path):
    db_path = tmp_path / "empty.db"
    fetcher = DataFetcher(db_path=str(db_path), config=AppConfig(db_path=db_path, remote_geocoding_enabled=False))
    fetcher.initialize_database()
    return db_path


@pytest.fixture
def db_columns(populated_db_path):
    with sqlite3.connect(populated_db_path) as conn:
        return conn.execute("PRAGMA table_info(listings)").fetchall()
