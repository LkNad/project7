import requests
import sqlite3
from typing import cast

from backend.DataFetcher import DataFetcher
from backend.config import AppConfig
from frontend.html_renderer import _display_coordinates


def test_parse_html_fixture_extracts_two_valid_listings(sample_html_path):
    fetcher = DataFetcher(source=str(sample_html_path))
    html = fetcher.fetch()

    listings = fetcher.parse(html)

    assert len(listings) == 2
    by_address = {item["address"]: item for item in listings}
    assert by_address["Москва, проспект Мира, 12"]["price"] == 12400000.0
    assert by_address["Москва, проспект Мира, 12"]["rooms"] == 2
    assert by_address["Москва, проспект Мира, 12"]["metro_station"] == "ВДНХ"
    assert by_address["Москва, проспект Мира, 12"]["image_url"] == "https://example.test/images/101.jpg"
    assert by_address["Москва, Комсомольский проспект, 21"]["url"] == "https://example.test/listings/102"
    assert by_address["Москва, Комсомольский проспект, 21"]["total_floors"] == 16


def test_parse_builtin_dataset_returns_normalized_items():
    fetcher = DataFetcher(source="test://default", config=AppConfig(remote_geocoding_enabled=False))

    listings = fetcher.parse(None)

    assert len(listings) == 200
    assert len({item["district"] for item in listings}) >= 8
    assert all(item["source"] for item in listings)
    assert all(item["price_per_m2"] > 0 for item in listings)
    assert all("geocode_status" in item for item in listings)
    assert all("map_point" in item for item in listings)
    assert any(item["metro_time_min"] is not None for item in listings)
    assert any(not item["image_url"] for item in listings)


def test_refresh_database_with_fixture_creates_reproducible_records(tmp_path, sample_html_path):
    db_path = tmp_path / "refresh.db"
    fetcher = DataFetcher(
        source=str(sample_html_path),
        db_path=str(db_path),
        config=AppConfig(db_path=db_path, remote_geocoding_enabled=False),
    )

    saved = fetcher.refresh_database(reset=True)

    assert len(saved) == 2
    loaded = fetcher.parse(fetcher.fetch())
    assert [item["address"] for item in loaded] == [item["address"] for item in saved]
    assert all(item["title"] for item in saved)


def test_remote_geocoder_stops_after_rate_limit():
    class FakeResponse:
        status_code = 429
        headers = {"Retry-After": "60"}

        def raise_for_status(self):
            raise requests.HTTPError("429 Client Error")

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def get(self, *args, **kwargs):
            self.calls += 1
            return FakeResponse()

    session = FakeSession()
    fetcher = DataFetcher(
        source="test://default",
        config=AppConfig(remote_geocoding_enabled=True, geocoder_min_delay=0),
        session=cast(requests.Session, session),
    )

    first = fetcher._request_geocoder("Москва, ул. Маршала Чуйкова, 18", "Кузьминки")
    second = fetcher._request_geocoder("Москва, Измайловский б-р, 56", "Измайлово")

    assert first is not None
    assert first["geocode_source"] == "deterministic-local"
    assert second is not None
    assert second["geocode_source"] == "deterministic-local"
    assert session.calls == 1


def test_build_geocoder_queries_expands_common_moscow_abbreviations():
    fetcher = DataFetcher(source="test://default", config=AppConfig(remote_geocoding_enabled=False))

    queries = fetcher._build_geocoder_queries("Москва, ВАО, Измайловский б-р, 56", "Измайлово")

    assert any("Измайловский бульвар, 56" in query for query in queries)
    assert any("район Измайлово" in query for query in queries)


def test_build_geocoder_queries_strips_inline_district_prefixes():
    fetcher = DataFetcher(source="test://default", config=AppConfig(remote_geocoding_enabled=False))

    queries = fetcher._build_geocoder_queries(
        "Москва, ЮАО, р-н Даниловский, Дербеневская наб., 27с24",
        "Даниловский",
    )

    assert any("Москва, Дербеневская" in query for query in queries)


def test_yandex_maps_geocoder_extracts_coordinates_from_html():
    class FakeResponse:
        status_code = 200
        text = '<html><script>window.state={"displayCoordinates":[37.645294,55.811477]}</script></html>'

        def raise_for_status(self):
            return None

    class FakeSession:
        def get(self, *args, **kwargs):
            return FakeResponse()

    fetcher = DataFetcher(
        source="test://default",
        config=AppConfig(remote_geocoding_enabled=True, geocoder_min_delay=0),
        session=cast(requests.Session, FakeSession()),
    )

    result = fetcher._request_yandex_maps_geocoder_raw("Москва, Староалексеевская ул., 5А")

    assert result is not None
    assert result["geocode_source"] == "yandex-maps"
    assert result["lat"] == 55.811477
    assert result["lon"] == 37.645294


def test_yandex_http_geocoder_extracts_coordinates_from_json():
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "response": {
                    "GeoObjectCollection": {
                        "featureMember": [
                            {"GeoObject": {"Point": {"pos": "37.645294 55.811477"}}}
                        ]
                    }
                }
            }

    class FakeSession:
        def get(self, *args, **kwargs):
            return FakeResponse()

    fetcher = DataFetcher(
        source="test://default",
        config=AppConfig(
            remote_geocoding_enabled=True,
            geocoder_min_delay=0,
            yandex_geocoder_key="test-key",
        ),
        session=cast(requests.Session, FakeSession()),
    )

    result = fetcher._request_yandex_http_geocoder_raw("Москва, Староалексеевская ул., 5А")

    assert result is not None
    assert result["geocode_source"] == "yandex-http"
    assert result["lat"] == 55.811477
    assert result["lon"] == 37.645294


def test_display_coordinates_returns_exact_point_for_provided_coords():
    lat, lon = _display_coordinates({
        "address": "Москва, проспект Мира, 12",
        "lat": 55.781234,
        "lon": 37.631234,
        "geocode_source": "source-payload",
        "geocode_status": "provided",
    })

    assert lat == 55.781234
    assert lon == 37.631234


def test_ensure_database_compatibility_upgrades_fallback_to_remote(tmp_path, sample_html_path):
    db_path = tmp_path / "upgrade_geocode.db"
    fetcher = DataFetcher(
        source="test://default",
        db_path=str(db_path),
        config=AppConfig(db_path=db_path, remote_geocoding_enabled=False),
    )
    fetcher.save_to_db([
        {
            "title": "Квартира у ВДНХ",
            "address": "Москва, проспект Мира, 12",
            "district": "Алексеевский",
            "price": 12400000,
            "rooms": 2,
            "area": 48.5,
            "lat": 0,
            "lon": 0,
            "source": "fixture",
        },
        {
            "title": "Квартира на Комсомольском",
            "address": "Москва, Комсомольский проспект, 21",
            "district": "Хамовники",
            "price": 21900000,
            "rooms": 3,
            "area": 81,
            "lat": 0,
            "lon": 0,
            "source": "fixture",
        },
    ])

    class FakeResponse:
        status_code = 200
        headers = {}

        def __init__(self, lat, lon):
            self.lat = lat
            self.lon = lon

        def raise_for_status(self):
            return None

        def json(self):
            return [{"lat": str(self.lat), "lon": str(self.lon), "importance": 0.93}]

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def get(self, *args, **kwargs):
            self.calls += 1
            query = ((kwargs.get("params") or {}).get("q") or "").lower()
            if "комсомольский" in query:
                return FakeResponse(55.7266, 37.5802)
            return FakeResponse(55.8108, 37.6387)

    session = FakeSession()
    fetcher_remote = DataFetcher(
        source="test://default",
        db_path=str(db_path),
        config=AppConfig(db_path=db_path, remote_geocoding_enabled=True, geocoder_min_delay=0),
        session=cast(requests.Session, session),
    )

    fetcher_remote.ensure_database_compatibility()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT geocode_source, lat, lon FROM listings ORDER BY id ASC").fetchall()

    assert rows
    assert all(row[0] == "nominatim" for row in rows)
    assert rows[0][1] == 55.8108
    assert rows[0][2] == 37.6387
    assert rows[1][1] == 55.7266
    assert rows[1][2] == 37.5802
    assert session.calls >= 1
