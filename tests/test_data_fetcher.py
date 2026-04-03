import requests
from typing import cast

from backend.DataFetcher import DataFetcher
from backend.config import AppConfig


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
