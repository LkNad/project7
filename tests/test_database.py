import sqlite3

from backend.DataFetcher import DataFetcher
from frontend.filters import load_data_from_db


def test_database_schema_matches_expected_columns(db_columns):
    column_names = [column[1] for column in db_columns]

    assert column_names == [
        "id",
        "title",
        "address",
        "price",
        "rooms",
        "district",
        "lat",
        "lon",
        "area",
        "floor",
        "total_floors",
        "price_per_m2",
        "url",
        "image_url",
        "description",
        "deal_type",
        "building_type",
        "metro_station",
        "metro_time_min",
        "geocode_status",
        "geocode_source",
        "geocode_confidence",
        "map_point",
        "source",
        "created_at",
    ]


def test_load_data_from_db_reads_runtime_demo_rows(demo_db_path):
    rows, error = load_data_from_db(db_path=str(demo_db_path))

    assert error is None
    assert len(rows) == 200
    assert all("created_at" in row for row in rows)
    assert all("price_per_m2" in row for row in rows)
    assert all("geocode_status" in row for row in rows)
    assert all("map_point" in row for row in rows)
    assert rows[0]["title"]


def test_district_table_is_populated(demo_db_path):
    with sqlite3.connect(demo_db_path) as conn:
        district_count = conn.execute("SELECT COUNT(*) FROM districts").fetchone()[0]

    assert district_count == 8


def test_empty_database_returns_no_rows(empty_db_path):
    rows, error = load_data_from_db(db_path=str(empty_db_path))

    assert error is None
    assert rows == []


def test_database_contains_same_number_of_rows_as_runtime_dataset(demo_db_path):
    with sqlite3.connect(demo_db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]

    assert count == 200


def test_legacy_database_is_migrated_on_read(tmp_path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                price REAL NOT NULL DEFAULT 0,
                rooms INTEGER NOT NULL DEFAULT 0,
                district TEXT NOT NULL DEFAULT 'Неизвестный',
                lat REAL NOT NULL DEFAULT 0,
                lon REAL NOT NULL DEFAULT 0,
                area REAL NOT NULL DEFAULT 0,
                floor INTEGER,
                url TEXT DEFAULT '',
                source TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO listings (address, price, rooms, district, lat, lon, area, floor, url, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("Москва, Тверская улица, 10", 15500000, 2, "Тверской", 55.751244, 37.618423, 54.3, 5, "https://example.test/1", "legacy"),
        )
        conn.commit()

    rows, error = load_data_from_db(db_path=str(db_path))

    assert error is None
    assert len(rows) == 1
    assert rows[0]["title"] == "Москва, Тверская улица, 10"

    with sqlite3.connect(db_path) as conn:
        columns = [column[1] for column in conn.execute("PRAGMA table_info(listings)").fetchall()]
        district_count = conn.execute("SELECT COUNT(*) FROM districts").fetchone()[0]

    assert "title" in columns
    assert "price_per_m2" in columns
    assert "geocode_status" in columns
    assert "map_point" in columns
    assert district_count == 1
