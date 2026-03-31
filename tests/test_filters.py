from frontend.filters import (
    DEFAULT_FILTERS,
    build_page_context,
    filter_listings,
    get_filter_options,
    load_data_from_db,
    normalize_filters,
)


def test_filter_listings_by_price_rooms_and_district(populated_db_path):
    listings, error = load_data_from_db(db_path=str(populated_db_path))

    assert error is None
    filtered = filter_listings(
        listings,
        {
            "price_range": [12_000_000, 13_000_000],
            "rooms": 2,
            "district": "Алексеевский",
            "chart_type": "bar",
        },
    )

    assert len(filtered) == 1
    assert filtered[0]["address"] == "Москва, проспект Мира, 12"


def test_normalize_filters_handles_reset_and_invalid_values():
    reset = normalize_filters({"action": "reset_filters"})
    invalid = normalize_filters(
        {
            "price_min": "5000000",
            "price_max": "1000000",
            "rooms": "bad-value",
            "district": "  Хамовники  ",
            "chart_type": "scatter",
        }
    )

    assert reset == DEFAULT_FILTERS
    assert invalid["price_range"] == [1_000_000, 5_000_000]
    assert invalid["rooms"] is None
    assert invalid["district"] == "Хамовники"
    assert invalid["chart_type"] == "bar"


def test_build_page_context_for_empty_database(empty_db_path):
    context = build_page_context(db_path=str(empty_db_path))

    assert context["status"]["kind"] == "empty"
    assert context["total_count"] == 0
    assert context["results_count"] == 0


def test_build_page_context_for_populated_database(populated_db_path):
    context = build_page_context(
        form={"price_min": "10000000", "price_max": "20000000", "chart_type": "table", "action": "apply_filters"},
        db_path=str(populated_db_path),
    )

    assert context["status"]["kind"] == "success"
    assert context["total_count"] == 2
    assert context["results_count"] == 1
    assert context["chart"]["type"] == "table"
    assert get_filter_options(context["listings"])["price_bounds"]["min"] >= 10_000_000
