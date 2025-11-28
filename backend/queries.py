# создание таблицы объявлений
CREATE_TABLE_LISTINGS = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT,
    price TEXT,
    total_meters TEXT,
    rooms_count TEXT,
    floor TEXT,
    floors_count TEXT,
    object_type TEXT,
    house_material_type TEXT,
    year_of_construction TEXT,
    district TEXT,
    underground TEXT,
    url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# вставка нового объявления
INSERT_LISTING = """
INSERT INTO listings 
(address, price, total_meters, rooms_count, floor, floors_count, 
 object_type, house_material_type, year_of_construction, district, 
 underground, url) 
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

# выбрать все объявления
SELECT_ALL_LISTINGS = """
SELECT id, address, price, total_meters, rooms_count, floor, floors_count, 
       object_type, house_material_type, year_of_construction, district, underground, url, created_at 
FROM listings;
"""

# выбрать объявления с фильтрацией по району
SELECT_BY_DISTRICT = """
SELECT id, address, price, total_meters, rooms_count, floor, floors_count, 
       object_type, house_material_type, year_of_construction, district, underground, url, created_at 
FROM listings 
WHERE district = ?;
"""

# удаление таблицы (для тестирования)
DROP_TABLE_LISTINGS = """
DROP TABLE IF EXISTS listings;
"""
