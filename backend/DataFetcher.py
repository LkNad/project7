# backend/DataFetcher.py
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from urllib.parse import urljoin, urlparse

import chardet
import requests
from bs4 import BeautifulSoup

from backend.config import AppConfig, DEFAULT_TEST_SOURCE_NAME, resolve_path
from backend.Listing import Listing
from backend.queries import CREATE_TABLE_LISTINGS, DROP_TABLE_LISTINGS, INSERT_LISTING


LOGGER = logging.getLogger(__name__)

TEST_DATASETS = {
    "default": {
        "html": """
        <html>
          <body>
            <section class="listing-card" data-lat="55.751244" data-lon="37.618423">
              <a class="listing-link" href="https://example.test/listing/1">Квартира у метро</a>
              <div class="listing-title">2-комнатная квартира, ул. Тверская, 10</div>
              <div class="listing-address">Москва, Тверская улица, 10</div>
              <div class="listing-price">15 500 000 ₽</div>
              <div class="listing-area">54.3 м²</div>
              <div class="listing-rooms">2 комнаты</div>
              <div class="listing-floor">5 этаж</div>
              <div class="listing-district">Тверской</div>
            </section>
            <article class="offer-item" data-lat="55.706100" data-lon="37.555400">
              <a class="offer-link" href="/listing/2">Апартаменты у набережной</a>
              <span class="address">Москва, Фрунзенская набережная, 30</span>
              <span class="price">22 300 000 ₽</span>
              <span class="rooms">3</span>
              <span class="area">78 м²</span>
              <span class="floor">9/14</span>
              <span class="district">Хамовники</span>
            </article>
          </body>
        </html>
        """,
        "items": [
            {
                "address": "Москва, Тверская улица, 10",
                "price": 15500000,
                "rooms": 2,
                "district": "Тверской",
                "lat": 55.751244,
                "lon": 37.618423,
                "area": 54.3,
                "floor": 5,
                "url": "https://example.test/listing/1",
            },
            {
                "address": "Москва, Фрунзенская набережная, 30",
                "price": 22300000,
                "rooms": 3,
                "district": "Хамовники",
                "lat": 55.706100,
                "lon": 37.555400,
                "area": 78,
                "floor": 9,
                "url": "https://example.test/listing/2",
            },
        ],
    }
}


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

        dataset = TEST_DATASETS.get(self.test_dataset_name) or TEST_DATASETS.get(str(self.source))
        if not dataset:
            LOGGER.error("Тестовый датасет не найден: %s", self.test_dataset_name or self.source)
            return None

        LOGGER.info("Используется встроенный тестовый датасет: %s", self.test_dataset_name or self.source)
        return dataset.get("html")

    def parse(self, html: str | None) -> list[dict]:
        """Извлекает данные из HTML или встроенного тестового набора."""
        if self.source_type == "test":
            dataset = TEST_DATASETS.get(self.test_dataset_name) or TEST_DATASETS.get(str(self.source))
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
            "url": urljoin(source_base, url_value) if url_value else "",
        }
        return payload

    def _parse_single_listing_page(self, soup: BeautifulSoup) -> Listing | None:
        payload = {
            "address": self._select_text(soup, ["h1", ".listing-address", ".address", "title"]),
            "price": self._select_text(soup, [".listing-price", ".price", "[itemprop='price']"]),
            "rooms": self._select_text(soup, [".listing-rooms", ".rooms"]),
            "district": self._select_text(soup, [".listing-district", ".district"]),
            "area": self._select_text(soup, [".listing-area", ".area"]),
            "floor": self._select_text(soup, [".listing-floor", ".floor"]),
            "url": self.source if self.source_type == "url" else "",
        }
        listing = Listing.from_raw(payload, source=self.source)
        return listing if listing.validate() else None

    def _normalize_listings(self, raw_items: list[dict]) -> list[dict]:
        listings = []
        for raw_item in raw_items:
            listing = Listing.from_raw(raw_item, source=DEFAULT_TEST_SOURCE_NAME)
            if listing.validate():
                listings.append(listing.to_dict())
        return listings

    def initialize_database(self) -> None:
        """Создаёт схему БД, если она отсутствует."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(CREATE_TABLE_LISTINGS)
            conn.commit()
        LOGGER.info("Схема БД инициализирована: %s", self.db_path)

    def refresh_database(self, listings: list[dict] | None = None, *, reset: bool = False) -> list[dict]:
        """Обновляет БД: при необходимости очищает таблицу и загружает актуальные данные."""
        self.initialize_database()
        data = listings if listings is not None else self.parse(self.fetch())

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if reset:
                cursor.execute(DROP_TABLE_LISTINGS)
                cursor.execute(CREATE_TABLE_LISTINGS)
            else:
                cursor.execute("DELETE FROM listings")

            for item in data:
                listing = Listing.from_raw(item, source=self.source)
                if listing.validate():
                    cursor.execute(INSERT_LISTING, listing.to_db_tuple())
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
            for item in listings:
                listing = Listing.from_raw(item, source=self.source)
                if listing.validate():
                    cur.execute(INSERT_LISTING, listing.to_db_tuple())
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
