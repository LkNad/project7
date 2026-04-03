import sqlite3
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_manage_data_rebuild_db_smoke(tmp_path):
    db_path = tmp_path / "cli-rebuild.db"

    result = subprocess.run(
        [
            sys.executable,
            "manage_data.py",
            "rebuild-db",
            "--source",
            "test://default",
            "--db-path",
            str(db_path),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "[manage_data] rebuilt DB ->" in result.stdout
    assert "[manage_data] source -> test://default" in result.stdout
    assert "[manage_data] remote geocoding -> False" in result.stdout
    assert db_path.exists()

    with sqlite3.connect(db_path) as conn:
        listing_count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        district_count = conn.execute("SELECT COUNT(*) FROM districts").fetchone()[0]

    assert listing_count == 200
    assert district_count == 8
