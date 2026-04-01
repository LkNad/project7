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
            "map_mode": "overall",
            "area_min": 40,
            "deal_type": None,
            "max_metro_time": 15,
            "min_district_score": 0,
            "min_object_score": 0,
            "undervalued_only": False,
            "family_friendly_only": False,
            "investment_friendly_only": False,
            "transport_priority_only": False,
            "compare_districts": [],
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
    assert invalid["map_mode"] == "overall"
    assert invalid["compare_districts"] == []
    assert invalid["shortlist_focus"] == "top"


def test_build_page_context_for_empty_database(empty_db_path):
    context = build_page_context(db_path=str(empty_db_path))

    assert context["status"]["kind"] == "empty"
    assert context["total_count"] == 0
    assert context["results_count"] == 0


def test_build_page_context_for_populated_database(demo_db_path):
    context = build_page_context(
        form={"price_min": "10000000", "price_max": "20000000", "chart_type": "table", "action": "apply_filters"},
        db_path=str(demo_db_path),
    )

    assert context["status"]["kind"] == "success"
    assert context["total_count"] == 200
    assert context["results_count"] > 0
    assert context["chart"]["type"] == "table"
    assert get_filter_options(context["listings"])["price_bounds"]["min"] >= 10_000_000
    assert context["listings"][0]["scores"]["object_score"] > 0
    assert context["districts"]
    assert context["shortlist"]
    assert context["map_context"]["has_map_data"] is True
    assert context["map_context"]["engine"] == "maplibre"
    assert context["map_context"]["scenario"]["key"] == "overall"
    assert context["map_context"]["scenario"]["workspace_title"]
    assert context["map_context"]["clustering"]["cluster_max_zoom"] == 13.6
    assert context["map_context"]["district_geojson"]["features"]
    assert len(context["map_context"]["story_points"]) == 3
    assert context["map_context"]["stats"]["listing_count"] > 0


def test_build_page_context_supports_compare_and_recommendations(demo_db_path):
    context = build_page_context(
        form={
            "price_min": "10000000",
            "price_max": "25000000",
            "map_mode": "investment",
            "compare_districts": ["Алексеевский", "Хамовники"],
            "action": "apply_filters",
        },
        db_path=str(demo_db_path),
    )

    assert context["compare"]["comparison"] is not None
    assert len(context["recommendations"]) >= 1
    assert context["recommendations"][0]["recommendation_reasons"]
    assert context["map_context"]["scenario"]["key"] == "investment"
    assert context["compare"]["comparison"]["scenario_cards"]


def test_build_page_context_reorders_shortlist_for_scenario_switch(demo_db_path):
    overall = build_page_context(
        form={"map_mode": "overall", "price_min": "10000000", "price_max": "25000000", "action": "apply_filters"},
        db_path=str(demo_db_path),
    )
    investment = build_page_context(
        form={"map_mode": "investment", "price_min": "10000000", "price_max": "25000000", "action": "apply_filters"},
        db_path=str(demo_db_path),
    )

    assert overall["map_context"]["scenario"]["key"] == "overall"
    assert investment["map_context"]["scenario"]["key"] == "investment"
    assert overall["map_context"]["scenario"]["listing_score_key"] == "object_score"
    assert investment["map_context"]["scenario"]["listing_score_key"] == "investment_score"
    assert overall["shortlist"] != investment["shortlist"]
