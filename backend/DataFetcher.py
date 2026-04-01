# backend/DataFetcher.py
from __future__ import annotations

import logging
import hashlib
import sqlite3
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse

import chardet
import requests
from bs4 import BeautifulSoup

from backend.config import AppConfig, DEFAULT_TEST_SOURCE_NAME, resolve_path
from backend.Listing import Listing
from backend.queries import (
    CREATE_TABLE_DISTRICTS,
    CREATE_TABLE_LISTINGS,
    DELETE_DISTRICTS,
    DISTRICT_COLUMN_DEFINITIONS,
    DROP_TABLE_DISTRICTS,
    DROP_TABLE_LISTINGS,
    INSERT_LISTING,
    LISTING_COLUMN_DEFINITIONS,
    UPSERT_DISTRICT,
)
from backend.scoring.engine import enrich_listings


LOGGER = logging.getLogger(__name__)

DISTRICT_CENTROIDS = {
    "Хамовники": (55.7285, 37.5794),
    "Пресненский": (55.7582, 37.5484),
    "Тверской": (55.7681, 37.6052),
    "Алексеевский": (55.8097, 37.6388),
    "Раменки": (55.7006, 37.5086),
    "Даниловский": (55.7088, 37.6251),
    "Сокольники": (55.7931, 37.6788),
    "Измайлово": (55.7906, 37.7819),
}

DIRTY_ADDRESS_RE = re.compile(r"^(nan|none|null|не указано|адрес не указан|без адреса|—|-|\d+)$", re.IGNORECASE)


def _build_demo_dataset() -> dict:
    district_profiles = [
        {
            "district": "Хамовники",
            "lat": 55.7285,
            "lon": 37.5794,
            "price_per_m2": 458000,
            "price_spread": 68000,
            "metro_station": "Фрунзенская",
            "metro_time": 7,
            "building_type": "монолитный",
            "streets": [
                "Комсомольский проспект",
                "Усачёва улица",
                "Ефремова улица",
                "Фрунзенская набережная",
            ],
            "scenario": "family",
            "room_mix": [2, 3, 3, 4],
        },
        {
            "district": "Пресненский",
            "lat": 55.7582,
            "lon": 37.5484,
            "price_per_m2": 424000,
            "price_spread": 62000,
            "metro_station": "Улица 1905 года",
            "metro_time": 6,
            "building_type": "монолитный",
            "streets": [
                "Шмитовский проезд",
                "Мантулинская улица",
                "Красная Пресня",
                "Большая Декабрьская улица",
            ],
            "scenario": "investment",
            "room_mix": [1, 2, 2, 3],
        },
        {
            "district": "Тверской",
            "lat": 55.7681,
            "lon": 37.6052,
            "price_per_m2": 391000,
            "price_spread": 54000,
            "metro_station": "Маяковская",
            "metro_time": 5,
            "building_type": "кирпичный",
            "streets": [
                "1-я Тверская-Ямская улица",
                "Лесная улица",
                "Новослободская улица",
                "Долгоруковская улица",
            ],
            "scenario": "transport",
            "room_mix": [1, 1, 2, 3],
        },
        {
            "district": "Алексеевский",
            "lat": 55.8097,
            "lon": 37.6388,
            "price_per_m2": 289000,
            "price_spread": 34000,
            "metro_station": "ВДНХ",
            "metro_time": 9,
            "building_type": "панельный",
            "streets": [
                "проспект Мира",
                "Новоалексеевская улица",
                "улица Павла Корчагина",
                "Маломосковская улица",
            ],
            "scenario": "balanced",
            "room_mix": [1, 2, 2, 3],
        },
        {
            "district": "Раменки",
            "lat": 55.7006,
            "lon": 37.5086,
            "price_per_m2": 337000,
            "price_spread": 42000,
            "metro_station": "Ломоносовский проспект",
            "metro_time": 8,
            "building_type": "монолитный",
            "streets": [
                "Мичуринский проспект",
                "улица Столетова",
                "Мосфильмовская улица",
                "улица Удальцова",
            ],
            "scenario": "family",
            "room_mix": [2, 3, 3, 4],
        },
        {
            "district": "Даниловский",
            "lat": 55.7088,
            "lon": 37.6251,
            "price_per_m2": 305000,
            "price_spread": 36000,
            "metro_station": "Тульская",
            "metro_time": 7,
            "building_type": "монолитный",
            "streets": [
                "Автозаводская улица",
                "Дубининская улица",
                "улица Серпуховский Вал",
                "Варшавское шоссе",
            ],
            "scenario": "investment",
            "room_mix": [1, 2, 2, 3],
        },
        {
            "district": "Сокольники",
            "lat": 55.7931,
            "lon": 37.6788,
            "price_per_m2": 276000,
            "price_spread": 30000,
            "metro_station": "Сокольники",
            "metro_time": 8,
            "building_type": "кирпичный",
            "streets": [
                "Русаковская улица",
                "улица Стромынка",
                "Маленковская улица",
                "2-я Сокольническая улица",
            ],
            "scenario": "transport",
            "room_mix": [1, 2, 3, 3],
        },
        {
            "district": "Измайлово",
            "lat": 55.7906,
            "lon": 37.7819,
            "price_per_m2": 241000,
            "price_spread": 26000,
            "metro_station": "Партизанская",
            "metro_time": 10,
            "building_type": "панельный",
            "streets": [
                "Измайловский проспект",
                "Первомайская улица",
                "Сиреневый бульвар",
                "Никитинская улица",
            ],
            "scenario": "value",
            "room_mix": [1, 2, 2, 3],
        },
    ]

    descriptors = {
        "family": "просторная квартира рядом с парком и школами",
        "investment": "ликвидный формат рядом с деловой активностью и метро",
        "transport": "динамичный лот с быстрым commute и удобным метро",
        "balanced": "сбалансированный вариант для жизни без резких компромиссов",
        "value": "рациональная покупка с заметным value signal внутри района",
    }
    total_per_district = 25
    demo_items = []
    html_blocks = ["<html><body><section class='demo-grid'>"]
    identifier = 1

    for district_index, profile in enumerate(district_profiles):
        for item_index in range(total_per_district):
            rooms = profile["room_mix"][item_index % len(profile["room_mix"])]
            area_base = {1: 38, 2: 56, 3: 77, 4: 104}[rooms]
            area = round(area_base + (item_index % 5) * 3.4 + district_index * 0.7, 1)
            floor = 2 + (item_index * 3 + district_index) % 22
            total_floors = max(floor + 2, 12 + (item_index % 11))
            ppm2 = profile["price_per_m2"] + ((item_index % 6) - 2.5) * (profile["price_spread"] / 3)
            if item_index % 9 == 0:
                ppm2 *= 0.9
            elif item_index % 7 == 0:
                ppm2 *= 1.08
            price = round(ppm2 * area, -3)
            lat = round(profile["lat"] + ((item_index % 5) - 2) * 0.0044 + district_index * 0.0003, 6)
            lon = round(profile["lon"] + (((item_index // 5) % 5) - 2) * 0.0051 + district_index * 0.0002, 6)
            street = profile["streets"][item_index % len(profile["streets"])]
            house = 4 + item_index * 2 + district_index
            metro_time = max(3, profile["metro_time"] + ((item_index % 4) - 1))
            title = f"{rooms}-комнатная квартира, {street}, {house}"
            address = f"Москва, {street}, {house}"
            image_url = "" if item_index % 6 == 0 else f"https://images.example.test/demo/{identifier}.jpg"
            description = (
                f"{descriptors[profile['scenario']].capitalize()}. "
                f"{profile['district']} — сценарий {profile['scenario']} с акцентом на метро {profile['metro_station'].lower()}."
            )
            url = f"https://example.test/listing/{identifier}"
            item = {
                "id": identifier,
                "title": title,
                "address": address,
                "price": price,
                "rooms": rooms,
                "district": profile["district"],
                "lat": lat,
                "lon": lon,
                "area": area,
                "floor": floor,
                "total_floors": total_floors,
                "description": description,
                "building_type": profile["building_type"],
                "metro_station": profile["metro_station"],
                "metro_time_min": metro_time,
                "image_url": image_url,
                "url": url,
                "deal_type": "sale",
                "source": "test://default",
            }
            demo_items.append(item)
            html_blocks.append(
                f"<article class='offer-item' data-lat='{lat}' data-lon='{lon}'>"
                f"<a class='offer-link' href='{url}'>{title}</a>"
                f"<span class='address'>{address}</span>"
                f"<span class='price'>{int(price):,} ₽</span>"
                f"<span class='rooms'>{rooms}</span>"
                f"<span class='area'>{area} м²</span>"
                f"<span class='floor'>{floor}/{total_floors}</span>"
                f"<span class='district'>{profile['district']}</span>"
                f"</article>"
            )
            identifier += 1

    html_blocks.append("</section></body></html>")
    return {"html": "".join(html_blocks), "items": demo_items}


TEST_DATASETS = {
    "default": _build_demo_dataset()
}


def _resolve_test_dataset(source: str | None, dataset_name: str | None) -> tuple[str | None, dict | None]:
    dataset_key = dataset_name or ""
    if dataset_key.startswith("test://"):
        dataset_key = dataset_key.split("://", 1)[1]
    source_key = str(source or "")
    if source_key.startswith("test://"):
        source_key = source_key.split("://", 1)[1]

    effective_key = dataset_key or source_key or None
    dataset = TEST_DATASETS.get(effective_key or "") if effective_key else None
    return effective_key, dataset


class DataFetcher:
    def __init__(
        self,
        source: str | None = None,
        db_path: str | None = None,
        *,
        source_type: str | None = None,
        timeout: float | None = None,
        test_dataset_name: str | None = None,
        config: AppConfig | None = None,
        session: requests.Session | None = None,
    ):
        self.config = config or AppConfig.from_env()
        self.source = source or self.config.test_dataset_name
        self.source_type = source_type or self._detect_source_type(self.source)
        self.db_path = str(resolve_path(db_path or self.config.db_path))
        self.timeout = timeout or self.config.request_timeout
        self.test_dataset_name = test_dataset_name or self.config.test_dataset_name
        self.session = session or requests.Session()

    def detect_encoding(self, file_path: str | Path) -> str:
        """Определяет кодировку файла."""
        with open(file_path, 'rb') as file:
            result = chardet.detect(file.read())
            encoding = result['encoding'] or 'utf-8'
            LOGGER.info(
                "Определена кодировка %s для %s (уверенность %.2f)",
                encoding,
                file_path,
                result['confidence'] or 0,
            )
            return encoding

    @staticmethod
    def normalize_address(address: str) -> str:
        cleaned = " ".join(str(address or "").replace("ё", "е").split()).strip(" ,;")
        cleaned = re.sub(r"\s*,\s*", ", ", cleaned)
        cleaned = re.sub(r"\bг\.?\s*москва\b", "Москва", cleaned, flags=re.IGNORECASE)
        if cleaned and not cleaned.lower().startswith("москва"):
            cleaned = f"Москва, {cleaned}"
        return cleaned

    @staticmethod
    def normalize_district(district: str) -> str:
        normalized = " ".join(str(district or "").split()).strip()
        return normalized or "Неизвестный"

    def _validate_address_quality(self, address: str, district: str) -> tuple[bool, str]:
        normalized_address = self.normalize_address(address)
        normalized_district = self.normalize_district(district)
        if not normalized_address or DIRTY_ADDRESS_RE.match(normalized_address):
            return False, "invalid"
        if len(normalized_address) < 10 or "," not in normalized_address:
            return False, "dirty"
        if normalized_district != "Неизвестный" and normalized_district not in DISTRICT_CENTROIDS:
            return False, "district_mismatch"
        return True, "pending"

    def _load_geocode_cache(self, conn: sqlite3.Connection | None) -> dict[str, dict[str, object]]:
        if conn is None or not self._table_exists(conn, "listings"):
            return {}
        rows = conn.execute(
            """
            SELECT address, lat, lon, geocode_status, geocode_source, geocode_confidence
            FROM listings
            WHERE COALESCE(TRIM(address), '') <> ''
            """
        ).fetchall()
        cache = {}
        for row in rows:
            normalized_address = self.normalize_address(row[0])
            if not normalized_address:
                continue
            cache[normalized_address] = {
                "lat": row[1] or 0.0,
                "lon": row[2] or 0.0,
                "geocode_status": row[3] or "pending",
                "geocode_source": row[4] or "db-cache",
                "geocode_confidence": row[5] or 0.0,
            }
        return cache

    def _request_geocoder(self, address: str, district: str) -> dict | None:
        centroid = DISTRICT_CENTROIDS.get(self.normalize_district(district))
        if not centroid:
            return None
        digest = hashlib.sha256(address.encode("utf-8")).hexdigest()
        lat_offset = ((int(digest[:6], 16) % 1000) / 1000 - 0.5) * 0.018
        lon_offset = ((int(digest[6:12], 16) % 1000) / 1000 - 0.5) * 0.022
        lat = round(centroid[0] + lat_offset, 6)
        lon = round(centroid[1] + lon_offset, 6)
        confidence = 0.92 if any(char.isdigit() for char in address) else 0.77
        return {
            "lat": lat,
            "lon": lon,
            "geocode_status": "geocoded",
            "geocode_source": "deterministic-local",
            "geocode_confidence": confidence,
            "map_point": f"{lat:.6f},{lon:.6f}",
        }

    def _apply_geocoding_pipeline(self, raw_items: list[dict], conn: sqlite3.Connection | None = None) -> list[dict]:
        cache = self._load_geocode_cache(conn)
        processed = []
        seen = set()
        for raw_item in raw_items:
            item = dict(raw_item)
            item["district"] = self.normalize_district(item.get("district"))
            item["address"] = self.normalize_address(item.get("address", ""))
            candidate = Listing.from_raw(item)
            dedupe_key = (candidate.address, candidate.price, candidate.rooms, candidate.district)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            if candidate.lat and candidate.lon:
                item.update({
                    "lat": candidate.lat,
                    "lon": candidate.lon,
                    "geocode_status": item.get("geocode_status") or "provided",
                    "geocode_source": item.get("geocode_source") or "source-payload",
                    "geocode_confidence": float(item.get("geocode_confidence") or 1.0),
                    "map_point": f"{candidate.lat:.6f},{candidate.lon:.6f}",
                })
                processed.append(item)
                continue

            quality_ok, status = self._validate_address_quality(item.get("address", ""), item.get("district", ""))
            cached = cache.get(item.get("address", ""))
            if cached and cached.get("lat") and cached.get("lon"):
                item.update({
                    "lat": cached["lat"],
                    "lon": cached["lon"],
                    "geocode_status": "cached-fallback" if not quality_ok else "cached",
                    "geocode_source": cached.get("geocode_source") or "db-cache",
                    "geocode_confidence": float(cached.get("geocode_confidence") or 0.7),
                    "map_point": f"{cached['lat']:.6f},{cached['lon']:.6f}",
                })
                processed.append(item)
                continue

            if not quality_ok:
                item.update({
                    "lat": 0.0,
                    "lon": 0.0,
                    "geocode_status": status,
                    "geocode_source": "quality-control",
                    "geocode_confidence": 0.0,
                    "map_point": "",
                })
                processed.append(item)
                continue

            geocoded = self._request_geocoder(item["address"], item["district"])
            if geocoded:
                item.update(geocoded)
            else:
                item.update({
                    "lat": 0.0,
                    "lon": 0.0,
                    "geocode_status": "missing",
                    "geocode_source": "geocoder-unavailable",
                    "geocode_confidence": 0.0,
                    "map_point": "",
                })
            processed.append(item)
        return processed

    @staticmethod
    def _detect_source_type(source: str | None) -> str:
        if not source:
            return "test"

        parsed = urlparse(source)
        if parsed.scheme in {"http", "https"}:
            return "url"
        if parsed.scheme == "test":
            return "test"
        if Path(source).suffix.lower() in {".html", ".htm", ".txt"} or Path(source).exists():
            return "file"
        return "test"

    def fetch(self) -> str | None:
        """Получает HTML из локального файла, URL или тестового набора."""
        if self.source_type == "file":
            file_path = resolve_path(self.source)
            LOGGER.info("Чтение локального HTML-источника: %s", file_path)
            if not file_path.exists() or not file_path.is_file():
                LOGGER.error("Локальный источник не найден: %s", file_path)
                return None

            encoding = self.detect_encoding(file_path)
            try:
                with open(file_path, 'r', encoding=encoding, errors='replace') as file:
                    content = file.read()
                    if not content.strip():
                        LOGGER.warning("Локальный источник пуст: %s", file_path)
                        return None
                    LOGGER.info("Локальный HTML успешно прочитан, размер: %s символов", len(content))
                    return content
            except OSError as error:
                LOGGER.exception("Ошибка при чтении файла %s: %s", file_path, error)
                return None

        if self.source_type == "url":
            LOGGER.info("Загрузка HTML по URL: %s", self.source)
            try:
                response = self.session.get(
                    self.source,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; MephiJuniorBot/1.0)"},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                content = response.text
                if not content or not content.strip():
                    LOGGER.warning("Удалённый источник вернул пустой ответ: %s", self.source)
                    return None
                LOGGER.info("Удалённый HTML успешно загружен, размер: %s символов", len(content))
                return content
            except requests.RequestException as error:
                LOGGER.exception("Ошибка загрузки URL %s: %s", self.source, error)
                return None

        _, dataset = _resolve_test_dataset(self.source, self.test_dataset_name)
        if not dataset:
            LOGGER.error("Тестовый датасет не найден: %s", self.test_dataset_name or self.source)
            return None

        LOGGER.info("Используется встроенный тестовый датасет: %s", self.test_dataset_name or self.source)
        return dataset.get("html")

    def parse(self, html: str | None) -> list[dict]:
        """Извлекает данные из HTML или встроенного тестового набора."""
        if self.source_type == "test":
            _, dataset = _resolve_test_dataset(self.source, self.test_dataset_name)
            if dataset and dataset.get("items"):
                listings = self._normalize_listings(dataset["items"])
                LOGGER.info("Загружено %s записей из тестового датасета", len(listings))
                return listings

        if not html or not html.strip():
            LOGGER.warning("parse() получил пустой HTML-контент")
            return []

        soup = BeautifulSoup(html, "html.parser")
        if not soup.find():
            LOGGER.warning("HTML не содержит валидной DOM-структуры")
            return []

        listings = []
        selectors = [
            "div.listing-item",
            "article.offer-item",
            "section.listing-card",
            "div[data-listing-id]",
            "article[data-id]",
            "li[class*='listing']",
        ]
        containers = self._collect_containers(soup, selectors)

        for item in containers:
            raw_payload = self._extract_listing_payload(item)
            listing = Listing.from_raw(raw_payload, source=self.source)
            if listing.validate():
                listings.append(listing.to_dict())

        if not listings:
            fallback_listing = self._parse_single_listing_page(soup)
            if fallback_listing and fallback_listing.validate():
                listings.append(fallback_listing.to_dict())

        LOGGER.info("Всего найдено %s объявлений", len(listings))
        return listings

    @staticmethod
    def clean_text(text):
        """Очищает текст от лишних пробелов и символов."""
        return ' '.join(text.split()).strip() if text else ""

    def _collect_containers(self, soup: BeautifulSoup, selectors: list[str]):
        containers = []
        seen = set()
        for selector in selectors:
            for item in soup.select(selector):
                key = id(item)
                if key not in seen:
                    seen.add(key)
                    containers.append(item)
        return containers

    def _select_text(self, node, selectors: list[str], *, attr: str | None = None) -> str:
        for selector in selectors:
            found = node.select_one(selector)
            if not found:
                continue
            if attr:
                value = found.get(attr)
            else:
                value = found.get_text(" ", strip=True)
            if value:
                return self.clean_text(value)
        return ""

    def _extract_listing_payload(self, item) -> dict:
        source_base = self.source if self.source_type == "url" else "https://example.test"
        url_value = self._select_text(
            item,
            [
                "a.listing-link",
                "a.offer-link",
                "a[href]",
            ],
            attr="href",
        )

        payload = {
            "title": self._select_text(item, [".listing-title", ".title", "h1", "h2", "h3"]),
            "address": self._select_text(
                item,
                [
                    ".listing-address",
                    ".address",
                    "[itemprop='address']",
                    "[data-role='address']",
                ],
            ) or self._select_text(item, [".listing-title", ".title", "h1", "h2", "h3"]),
            "price": self._select_text(
                item,
                [
                    ".listing-price",
                    ".price",
                    "[itemprop='price']",
                    "[data-role='price']",
                ],
            ),
            "rooms": self._select_text(item, [".listing-rooms", ".rooms", "[data-role='rooms']"]),
            "district": self._select_text(item, [".listing-district", ".district", "[data-role='district']"]),
            "area": self._select_text(item, [".listing-area", ".area", "[data-role='area']"]),
            "floor": self._select_text(item, [".listing-floor", ".floor", "[data-role='floor']"]),
            "lat": item.get("data-lat") or item.get("data-latitude") or "",
            "lon": item.get("data-lon") or item.get("data-longitude") or "",
            "description": self._select_text(item, [".listing-description", ".description", "[data-role='description']"]),
            "image_url": self._select_text(item, ["img"], attr="src"),
            "metro_station": self._select_text(item, [".listing-metro", ".metro", "[data-role='metro']"]),
            "metro_time_min": self._select_text(item, [".listing-metro-time", ".metro-time", "[data-role='metro-time']"]),
            "building_type": self._select_text(item, [".listing-building", ".building-type", "[data-role='building-type']"]),
            "deal_type": self._select_text(item, [".listing-deal-type", "[data-role='deal-type']"]) or "sale",
            "url": urljoin(source_base, url_value) if url_value else "",
        }
        floor_value = payload.get("floor", "")
        if "/" in floor_value:
            floor_parts = floor_value.split("/", 1)
            payload["floor"] = floor_parts[0]
            payload["total_floors"] = floor_parts[1]
        return payload

    def _parse_single_listing_page(self, soup: BeautifulSoup) -> Listing | None:
        payload = {
            "title": self._select_text(soup, ["h1", ".listing-title", ".title", "title"]),
            "address": self._select_text(soup, ["h1", ".listing-address", ".address", "title"]),
            "price": self._select_text(soup, [".listing-price", ".price", "[itemprop='price']"]),
            "rooms": self._select_text(soup, [".listing-rooms", ".rooms"]),
            "district": self._select_text(soup, [".listing-district", ".district"]),
            "area": self._select_text(soup, [".listing-area", ".area"]),
            "floor": self._select_text(soup, [".listing-floor", ".floor"]),
            "description": self._select_text(soup, [".listing-description", ".description", "meta[name='description']"], attr="content"),
            "url": self.source if self.source_type == "url" else "",
        }
        listing = Listing.from_raw(payload, source=self.source)
        return listing if listing.validate() else None

    def _normalize_listings(self, raw_items: list[dict]) -> list[dict]:
        listings = []
        for raw_item in self._apply_geocoding_pipeline(raw_items):
            listing = Listing.from_raw(raw_item, source=DEFAULT_TEST_SOURCE_NAME)
            if listing.validate():
                listings.append(listing.to_dict())
        return listings

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
        return bool(row)

    @staticmethod
    def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
        if not DataFetcher._table_exists(conn, table_name):
            return set()
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {row[1] for row in rows}

    def _ensure_table_columns(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        definitions: dict[str, str],
        *,
        create_sql: str,
    ) -> bool:
        changed = False
        if not self._table_exists(conn, table_name):
            conn.execute(create_sql)
            return True

        existing_columns = self._get_table_columns(conn, table_name)
        for column_name, definition in definitions.items():
            if column_name in existing_columns:
                continue
            if "PRIMARY KEY" in definition.upper():
                continue
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
            changed = True
            LOGGER.warning(
                "В БД %s обнаружена legacy-схема: в таблицу %s добавлен столбец %s",
                self.db_path,
                table_name,
                column_name,
            )
        return changed

    def _backfill_listing_derived_fields(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            UPDATE listings
            SET title = COALESCE(NULLIF(title, ''), address, 'Без названия')
            WHERE COALESCE(title, '') = ''
            """
        )
        conn.execute(
            """
            UPDATE listings
            SET district = 'Неизвестный'
            WHERE COALESCE(TRIM(district), '') = ''
            """
        )
        conn.execute(
            """
            UPDATE listings
            SET deal_type = COALESCE(NULLIF(deal_type, ''), 'sale'),
                building_type = COALESCE(NULLIF(building_type, ''), 'Не указано'),
                source = COALESCE(source, ''),
                image_url = COALESCE(image_url, ''),
                description = COALESCE(description, ''),
                metro_station = COALESCE(metro_station, '')
            """
        )
        conn.execute(
            """
            UPDATE listings
            SET price_per_m2 = CASE
                WHEN COALESCE(price_per_m2, 0) > 0 THEN price_per_m2
                WHEN COALESCE(area, 0) > 0 THEN ROUND(price / area, 2)
                ELSE 0
            END
            """
        )
        conn.execute(
            """
            UPDATE listings
            SET geocode_status = CASE
                    WHEN COALESCE(TRIM(geocode_status), '') = '' AND lat != 0 AND lon != 0 THEN 'cached'
                    WHEN COALESCE(TRIM(geocode_status), '') = '' THEN 'missing'
                    ELSE geocode_status
                END,
                geocode_source = COALESCE(geocode_source, ''),
                geocode_confidence = COALESCE(geocode_confidence, 0),
                map_point = CASE WHEN lat != 0 AND lon != 0 THEN printf('%.6f,%.6f', lat, lon) ELSE '' END
            """
        )

    def _refresh_missing_coordinates(self, conn: sqlite3.Connection) -> int:
        rows = conn.execute(
            """
            SELECT id, address, district, price, rooms
            FROM listings
            WHERE COALESCE(lat, 0) = 0 OR COALESCE(lon, 0) = 0
            """
        ).fetchall()
        updated = 0
        for row in rows:
            payload = self._apply_geocoding_pipeline([
                {"address": row[1], "district": row[2], "price": row[3], "rooms": row[4]}
            ], conn=conn)[0]
            conn.execute(
                """
                UPDATE listings
                SET lat = ?, lon = ?, geocode_status = ?, geocode_source = ?, geocode_confidence = ?, map_point = ?
                WHERE id = ?
                """,
                (
                    payload.get("lat", 0.0),
                    payload.get("lon", 0.0),
                    payload.get("geocode_status", "missing"),
                    payload.get("geocode_source", ""),
                    payload.get("geocode_confidence", 0.0),
                    payload.get("map_point", ""),
                    row[0],
                ),
            )
            updated += 1
        return updated

    def _load_listings_from_connection(self, conn: sqlite3.Connection) -> list[dict]:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM listings ORDER BY created_at DESC, id DESC").fetchall()
        return [Listing.from_row(row).to_dict() for row in rows]

    def _rebuild_districts(self, conn: sqlite3.Connection) -> None:
        self._ensure_table_columns(
            conn,
            "districts",
            DISTRICT_COLUMN_DEFINITIONS,
            create_sql=CREATE_TABLE_DISTRICTS,
        )
        conn.execute(DELETE_DISTRICTS)
        listings = self._load_listings_from_connection(conn)
        _, districts, _ = enrich_listings(listings)
        for district in districts:
            conn.execute(
                UPSERT_DISTRICT,
                (
                    district["district"],
                    district["listing_count"],
                    district["avg_price"],
                    district["avg_price_per_m2"],
                    district["avg_area"],
                    district["avg_rooms"],
                    district["transport_score"],
                    district["infra_score"],
                    district["family_score"],
                    district["investment_score"],
                    district["district_score"],
                    district["budget_fit_score"],
                    district["quality_band"],
                    district["profile_label"],
                    "; ".join(district["highlights"]),
                ),
            )

    def ensure_database_compatibility(self) -> bool:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        schema_changed = False
        with sqlite3.connect(self.db_path) as conn:
            schema_changed |= self._ensure_table_columns(
                conn,
                "listings",
                LISTING_COLUMN_DEFINITIONS,
                create_sql=CREATE_TABLE_LISTINGS,
            )
            schema_changed |= self._ensure_table_columns(
                conn,
                "districts",
                DISTRICT_COLUMN_DEFINITIONS,
                create_sql=CREATE_TABLE_DISTRICTS,
            )
            self._backfill_listing_derived_fields(conn)
            self._refresh_missing_coordinates(conn)
            self._rebuild_districts(conn)
            conn.commit()
        return schema_changed

    def has_any_listings(self) -> bool:
        if not Path(self.db_path).exists():
            return False
        with sqlite3.connect(self.db_path) as conn:
            if not self._table_exists(conn, "listings"):
                return False
            row = conn.execute("SELECT COUNT(*) FROM listings").fetchone()
            return bool(row and row[0] > 0)

    def _get_runtime_stats(self) -> dict[str, object]:
        if not Path(self.db_path).exists():
            return {"listing_count": 0, "district_count": 0, "sources": set()}

        with sqlite3.connect(self.db_path) as conn:
            if not self._table_exists(conn, "listings"):
                return {"listing_count": 0, "district_count": 0, "sources": set()}

            listing_count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
            district_count = conn.execute("SELECT COUNT(DISTINCT district) FROM listings").fetchone()[0]
            source_rows = conn.execute(
                "SELECT DISTINCT COALESCE(NULLIF(source, ''), '__empty__') FROM listings"
            ).fetchall()
            return {
                "listing_count": listing_count,
                "district_count": district_count,
                "sources": {row[0] for row in source_rows},
            }

    def _needs_test_dataset_refresh(self, source: str | None) -> bool:
        effective_source = source or self.source or self.test_dataset_name
        if self._detect_source_type(effective_source) != "test":
            return False

        dataset_key, dataset = _resolve_test_dataset(effective_source, self.test_dataset_name)
        if not dataset:
            return False

        stats = self._get_runtime_stats()
        expected_listing_count = len(dataset.get("items") or [])
        expected_district_count = len({item.get("district") for item in dataset.get("items") or [] if item.get("district")})

        if stats["listing_count"] != expected_listing_count:
            LOGGER.warning(
                "Runtime-БД %s содержит %s объявлений вместо %s для dataset %s",
                self.db_path,
                stats["listing_count"],
                expected_listing_count,
                dataset_key,
            )
            return True
        if stats["district_count"] != expected_district_count:
            LOGGER.warning(
                "Runtime-БД %s содержит %s районов вместо %s для dataset %s",
                self.db_path,
                stats["district_count"],
                expected_district_count,
                dataset_key,
            )
            return True
        if stats["sources"] != {DEFAULT_TEST_SOURCE_NAME}:
            LOGGER.warning(
                "Runtime-БД %s использует источники %s вместо %s",
                self.db_path,
                sorted(stats["sources"]),
                DEFAULT_TEST_SOURCE_NAME,
            )
            return True
        return False

    def ensure_runtime_database(self, source: str | None = None, *, bootstrap_if_empty: bool = True) -> bool:
        schema_changed = self.ensure_database_compatibility()
        needs_refresh = self._needs_test_dataset_refresh(source)
        if bootstrap_if_empty and (not self.has_any_listings() or needs_refresh):
            effective_source = source or self.source or self.test_dataset_name
            LOGGER.warning(
                "База %s требует автозаполнения/пересборки из %s",
                self.db_path,
                effective_source,
            )
            self.source = effective_source
            self.source_type = self._detect_source_type(self.source)
            self.refresh_database(reset=True)
            return True
        return schema_changed

    def initialize_database(self) -> None:
        """Создаёт схему БД, если она отсутствует."""
        self.ensure_database_compatibility()
        LOGGER.info("Схема БД инициализирована: %s", self.db_path)

    def refresh_database(self, listings: list[dict] | None = None, *, reset: bool = False) -> list[dict]:
        """Обновляет БД: при необходимости очищает таблицу и загружает актуальные данные."""
        self.initialize_database()
        data = listings if listings is not None else self.parse(self.fetch())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if reset:
                cursor.execute(DROP_TABLE_DISTRICTS)
                cursor.execute(DROP_TABLE_LISTINGS)
                cursor.execute(CREATE_TABLE_LISTINGS)
                cursor.execute(CREATE_TABLE_DISTRICTS)
            else:
                cursor.execute(DELETE_DISTRICTS)
                cursor.execute("DELETE FROM listings")

            data = self._apply_geocoding_pipeline(data, conn=conn)
            for item in data:
                listing = Listing.from_raw(item, source=self.source)
                if listing.validate():
                    cursor.execute(INSERT_LISTING, listing.to_db_tuple())

            self._backfill_listing_derived_fields(conn)
            self._refresh_missing_coordinates(conn)
            self._rebuild_districts(conn)
            conn.commit()

        LOGGER.info("База данных %s обновлена, записей: %s", self.db_path, len(data))
        return data

    def save_to_db(self, listings):
        """Сохраняет данные в SQLite с поддержкой всех полей."""
        if not listings:
            LOGGER.warning("Нет данных для сохранения в БД")
            return

        self.initialize_database()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            listings = self._apply_geocoding_pipeline(listings, conn=conn)
            for item in listings:
                listing = Listing.from_raw(item, source=self.source)
                if listing.validate():
                    cur.execute(INSERT_LISTING, listing.to_db_tuple())
            self._backfill_listing_derived_fields(conn)
            self._refresh_missing_coordinates(conn)
            self._rebuild_districts(conn)
            conn.commit()
        LOGGER.info("Сохранено %s записей в базу %s", len(listings), self.db_path)

    def run(self):
        """Полный цикл: получить HTML, распарсить и сохранить в БД."""
        html = self.fetch()
        if html:
            data = self.parse(html)
            if data:
                self.save_to_db(data)
            else:
                LOGGER.warning("Не найдено данных для сохранения")
        else:
            LOGGER.warning("Не удалось получить HTML-контент")


def initialize_database(
    source: str | None = None,
    db_path: str | None = None,
    **kwargs,
) -> DataFetcher:
    fetcher = DataFetcher(source=source, db_path=db_path, **kwargs)
    fetcher.initialize_database()
    return fetcher


def refresh_database(
    source: str | None = None,
    db_path: str | None = None,
    *,
    reset: bool = False,
    **kwargs,
) -> list[dict]:
    fetcher = DataFetcher(source=source, db_path=db_path, **kwargs)
    return fetcher.refresh_database(reset=reset)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    refresh_database(source="test://default", reset=True)
