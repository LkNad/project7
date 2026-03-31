import sqlite3

from frontend.filters import load_data_from_db


def test_database_schema_matches_expected_columns(db_columns):
    column_names = [column[1] for column in db_columns]

    assert column_names == [
        "id",
        "address",
        "price",
        "rooms",
        "district",
        "lat",
        "lon",
        "area",
        "floor",
        "url",
        "source",
        "created_at",
    ]


def test_load_data_from_db_reads_inserted_rows(populated_db_path):
    rows, error = load_data_from_db(db_path=str(populated_db_path))

    assert error is None
    assert len(rows) == 2
    assert all("created_at" in row for row in rows)


def test_empty_database_returns_no_rows(empty_db_path):
    rows, error = load_data_from_db(db_path=str(empty_db_path))

    assert error is None
    assert rows == []


def test_database_contains_same_number_of_rows_as_fixture(populated_db_path):
    with sqlite3.connect(populated_db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]

    assert count == 2
