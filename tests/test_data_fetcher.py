from backend.DataFetcher import DataFetcher


def test_parse_html_fixture_extracts_two_valid_listings(sample_html_path):
    fetcher = DataFetcher(source=str(sample_html_path))
    html = fetcher.fetch()

    listings = fetcher.parse(html)

    assert len(listings) == 2
    by_address = {item["address"]: item for item in listings}
    assert by_address["Москва, проспект Мира, 12"]["price"] == 12400000.0
    assert by_address["Москва, проспект Мира, 12"]["rooms"] == 2
    assert by_address["Москва, Комсомольский проспект, 21"]["url"] == "https://example.test/listings/102"


def test_parse_builtin_dataset_returns_normalized_items():
    fetcher = DataFetcher(source="test://default")

    listings = fetcher.parse(None)

    assert len(listings) == 2
    assert {item["district"] for item in listings} == {"Тверской", "Хамовники"}
    assert all(item["source"] for item in listings)


def test_refresh_database_with_fixture_creates_reproducible_records(tmp_path, sample_html_path):
    db_path = tmp_path / "refresh.db"
    fetcher = DataFetcher(source=str(sample_html_path), db_path=str(db_path))

    saved = fetcher.refresh_database(reset=True)

    assert len(saved) == 2
    loaded = fetcher.parse(fetcher.fetch())
    assert [item["address"] for item in loaded] == [item["address"] for item in saved]
