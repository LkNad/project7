# backend/queries.py

LISTING_COLUMNS = """
    id,
    address,
    price,
    rooms,
    district,
    lat,
    lon,
    area,
    floor,
    url,
    source,
    created_at
"""

CREATE_TABLE_LISTINGS = """
CREATE TABLE IF NOT EXISTS listings (
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
);
"""

INSERT_LISTING = """
INSERT INTO listings (
    address,
    price,
    rooms,
    district,
    lat,
    lon,
    area,
    floor,
    url,
    source,
    created_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP));
"""

SELECT_ALL_LISTINGS = f"""
SELECT {LISTING_COLUMNS}
FROM listings
ORDER BY created_at DESC, id DESC;
"""

SELECT_BY_DISTRICT = f"""
SELECT {LISTING_COLUMNS}
FROM listings
WHERE district = ?
ORDER BY created_at DESC, id DESC;
"""

DROP_TABLE_LISTINGS = """
DROP TABLE IF EXISTS listings;
"""
