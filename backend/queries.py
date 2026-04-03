# backend/queries.py

LISTING_COLUMNS = """
    id,
    title,
    address,
    price,
    rooms,
    district,
    lat,
    lon,
    area,
    floor,
    total_floors,
    price_per_m2,
    url,
    image_url,
    description,
    deal_type,
    building_type,
    metro_station,
    metro_time_min,
    geocode_status,
    geocode_source,
    geocode_confidence,
    map_point,
    source,
    created_at
"""

LISTING_COLUMN_DEFINITIONS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "title": "TEXT NOT NULL DEFAULT ''",
    "address": "TEXT NOT NULL",
    "price": "REAL NOT NULL DEFAULT 0",
    "rooms": "INTEGER NOT NULL DEFAULT 0",
    "district": "TEXT NOT NULL DEFAULT 'Неизвестный'",
    "lat": "REAL NOT NULL DEFAULT 0",
    "lon": "REAL NOT NULL DEFAULT 0",
    "area": "REAL NOT NULL DEFAULT 0",
    "floor": "INTEGER",
    "total_floors": "INTEGER",
    "price_per_m2": "REAL NOT NULL DEFAULT 0",
    "url": "TEXT DEFAULT ''",
    "image_url": "TEXT DEFAULT ''",
    "description": "TEXT DEFAULT ''",
    "deal_type": "TEXT NOT NULL DEFAULT 'sale'",
    "building_type": "TEXT NOT NULL DEFAULT 'Не указано'",
    "metro_station": "TEXT DEFAULT ''",
    "metro_time_min": "INTEGER",
    "geocode_status": "TEXT NOT NULL DEFAULT 'pending'",
    "geocode_source": "TEXT NOT NULL DEFAULT ''",
    "geocode_confidence": "REAL NOT NULL DEFAULT 0",
    "map_point": "TEXT NOT NULL DEFAULT ''",
    "source": "TEXT DEFAULT ''",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

DISTRICT_COLUMN_DEFINITIONS = {
    "district": "TEXT PRIMARY KEY",
    "listing_count": "INTEGER NOT NULL DEFAULT 0",
    "avg_price": "REAL NOT NULL DEFAULT 0",
    "avg_price_per_m2": "REAL NOT NULL DEFAULT 0",
    "avg_area": "REAL NOT NULL DEFAULT 0",
    "avg_rooms": "REAL NOT NULL DEFAULT 0",
    "transport_score": "REAL NOT NULL DEFAULT 0",
    "infra_score": "REAL NOT NULL DEFAULT 0",
    "family_score": "REAL NOT NULL DEFAULT 0",
    "investment_score": "REAL NOT NULL DEFAULT 0",
    "district_score": "REAL NOT NULL DEFAULT 0",
    "budget_fit_score": "REAL NOT NULL DEFAULT 0",
    "quality_band": "TEXT NOT NULL DEFAULT ''",
    "profile_label": "TEXT NOT NULL DEFAULT ''",
    "highlights": "TEXT NOT NULL DEFAULT ''",
    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

DISTRICT_COLUMNS = """
    district,
    listing_count,
    avg_price,
    avg_price_per_m2,
    avg_area,
    avg_rooms,
    transport_score,
    infra_score,
    family_score,
    investment_score,
    district_score,
    budget_fit_score,
    quality_band,
    profile_label,
    highlights,
    updated_at
"""

SAVED_LIST_COLUMN_DEFINITIONS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "visitor_id": "TEXT NOT NULL",
    "listing_id": "INTEGER NOT NULL",
    "listing_key": "TEXT NOT NULL DEFAULT ''",
    "list_type": "TEXT NOT NULL",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

PRICE_SNAPSHOT_COLUMN_DEFINITIONS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "snapshot_key": "TEXT NOT NULL",
    "address": "TEXT NOT NULL",
    "district": "TEXT NOT NULL",
    "price": "REAL NOT NULL DEFAULT 0",
    "source": "TEXT DEFAULT ''",
    "captured_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

CREATE_TABLE_LISTINGS = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL,
    price REAL NOT NULL DEFAULT 0,
    rooms INTEGER NOT NULL DEFAULT 0,
    district TEXT NOT NULL DEFAULT 'Неизвестный',
    lat REAL NOT NULL DEFAULT 0,
    lon REAL NOT NULL DEFAULT 0,
    area REAL NOT NULL DEFAULT 0,
    floor INTEGER,
    total_floors INTEGER,
    price_per_m2 REAL NOT NULL DEFAULT 0,
    url TEXT DEFAULT '',
    image_url TEXT DEFAULT '',
    description TEXT DEFAULT '',
    deal_type TEXT NOT NULL DEFAULT 'sale',
    building_type TEXT NOT NULL DEFAULT 'Не указано',
    metro_station TEXT DEFAULT '',
    metro_time_min INTEGER,
    geocode_status TEXT NOT NULL DEFAULT 'pending',
    geocode_source TEXT NOT NULL DEFAULT '',
    geocode_confidence REAL NOT NULL DEFAULT 0,
    map_point TEXT NOT NULL DEFAULT '',
    source TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_TABLE_DISTRICTS = """
CREATE TABLE IF NOT EXISTS districts (
    district TEXT PRIMARY KEY,
    listing_count INTEGER NOT NULL DEFAULT 0,
    avg_price REAL NOT NULL DEFAULT 0,
    avg_price_per_m2 REAL NOT NULL DEFAULT 0,
    avg_area REAL NOT NULL DEFAULT 0,
    avg_rooms REAL NOT NULL DEFAULT 0,
    transport_score REAL NOT NULL DEFAULT 0,
    infra_score REAL NOT NULL DEFAULT 0,
    family_score REAL NOT NULL DEFAULT 0,
    investment_score REAL NOT NULL DEFAULT 0,
    district_score REAL NOT NULL DEFAULT 0,
    budget_fit_score REAL NOT NULL DEFAULT 0,
    quality_band TEXT NOT NULL DEFAULT '',
    profile_label TEXT NOT NULL DEFAULT '',
    highlights TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_TABLE_SAVED_LISTS = """
CREATE TABLE IF NOT EXISTS saved_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visitor_id TEXT NOT NULL,
    listing_id INTEGER NOT NULL,
    listing_key TEXT NOT NULL DEFAULT '',
    list_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(visitor_id, listing_key, list_type)
);
"""

CREATE_TABLE_PRICE_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS listing_price_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_key TEXT NOT NULL,
    address TEXT NOT NULL,
    district TEXT NOT NULL,
    price REAL NOT NULL DEFAULT 0,
    source TEXT DEFAULT '',
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

INSERT_LISTING = """
INSERT INTO listings (
    title,
    address,
    price,
    rooms,
    district,
    lat,
    lon,
    area,
    floor,
    total_floors,
    price_per_m2,
    url,
    image_url,
    description,
    deal_type,
    building_type,
    metro_station,
    metro_time_min,
    geocode_status,
    geocode_source,
    geocode_confidence,
    map_point,
    source,
    created_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP));
"""

UPSERT_DISTRICT = """
INSERT INTO districts (
    district,
    listing_count,
    avg_price,
    avg_price_per_m2,
    avg_area,
    avg_rooms,
    transport_score,
    infra_score,
    family_score,
    investment_score,
    district_score,
    budget_fit_score,
    quality_band,
    profile_label,
    highlights,
    updated_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
ON CONFLICT(district) DO UPDATE SET
    listing_count = excluded.listing_count,
    avg_price = excluded.avg_price,
    avg_price_per_m2 = excluded.avg_price_per_m2,
    avg_area = excluded.avg_area,
    avg_rooms = excluded.avg_rooms,
    transport_score = excluded.transport_score,
    infra_score = excluded.infra_score,
    family_score = excluded.family_score,
    investment_score = excluded.investment_score,
    district_score = excluded.district_score,
    budget_fit_score = excluded.budget_fit_score,
    quality_band = excluded.quality_band,
    profile_label = excluded.profile_label,
    highlights = excluded.highlights,
    updated_at = CURRENT_TIMESTAMP;
"""

DELETE_DISTRICTS = "DELETE FROM districts;"

SELECT_ALL_LISTINGS = f"""
SELECT {LISTING_COLUMNS}
FROM listings
ORDER BY created_at DESC, id DESC;
"""

SELECT_ALL_DISTRICTS = f"""
SELECT {DISTRICT_COLUMNS}
FROM districts
ORDER BY district_score DESC, listing_count DESC, district ASC;
"""

SELECT_BY_DISTRICT = f"""
SELECT {LISTING_COLUMNS}
FROM listings
WHERE district = ?
ORDER BY created_at DESC, id DESC;
"""

DROP_TABLE_LISTINGS = "DROP TABLE IF EXISTS listings;"
DROP_TABLE_DISTRICTS = "DROP TABLE IF EXISTS districts;"
