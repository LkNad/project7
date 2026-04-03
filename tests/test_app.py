from main.app import create_app


def _set_csrf(client, token="test-csrf-token"):
    with client.session_transaction() as session_state:
        session_state["_csrf_token"] = token
    return token


def test_index_page_renders_success_state_with_test_database(demo_db_path):
    app = create_app({"TESTING": True, "DB_PATH": str(demo_db_path)})
    client = app.test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Сценарий" in html
    assert "value-зона" in html
    assert "В базе 200 объявлений" in html
    assert "Подбор" in html
    assert "Сравнение районов" in html
    assert "Лучший район" in html


def test_map_page_renders_fullscreen_workspace(demo_db_path):
    app = create_app({"TESTING": True, "DB_PATH": str(demo_db_path)})
    client = app.test_client()

    response = client.get("/map")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "listings-map" in html
    assert "maplibre-gl" in html
    assert '"engine": "maplibre"' in html or '"engine":"maplibre"' in html
    assert "Панель карты" in html


def test_index_page_renders_empty_state_for_empty_database(empty_db_path):
    app = create_app({"TESTING": True, "DB_PATH": str(empty_db_path)})
    client = app.test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Данные пока отсутствуют" in html
    assert "Сравнение районов" in html


def test_index_page_applies_post_filters(populated_db_path):
    app = create_app({"TESTING": True, "DB_PATH": str(populated_db_path)})
    client = app.test_client()
    csrf_token = _set_csrf(client)

    response = client.post(
        "/",
        data={
            "_csrf_token": csrf_token,
            "price_min": "18000000",
            "price_max": "30000000",
            "rooms": "3",
            "district": "Хамовники",
            "chart_type": "bar",
            "action": "apply_filters",
        },
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Подборка объектов" in html
    assert "Москва, Комсомольский проспект, 21" in html
    assert "Москва, проспект Мира, 12" not in html


def test_analytics_page_updates_scenario_context(populated_db_path):
    app = create_app({"TESTING": True, "DB_PATH": str(populated_db_path)})
    client = app.test_client()
    csrf_token = _set_csrf(client)

    response = client.post(
        "/analytics",
        data={
            "_csrf_token": csrf_token,
            "map_mode": "investment",
            "price_min": "10000000",
            "price_max": "25000000",
            "action": "apply_filters",
        },
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Инвестиционная карта ликвидности и потенциала" in html
    assert "Для инвестиций" in html


def test_api_routes_return_enriched_payload(demo_db_path):
    app = create_app({"TESTING": True, "DB_PATH": str(demo_db_path)})
    client = app.test_client()

    listings_response = client.get("/api/listings?price_min=10000000&price_max=25000000")
    districts_response = client.get("/api/districts")
    recommendations_response = client.get("/api/recommendations")
    compare_response = client.get("/api/compare?compare_districts=Алексеевский&compare_districts=Хамовники")

    assert listings_response.status_code == 200
    assert districts_response.status_code == 200
    assert recommendations_response.status_code == 200
    assert compare_response.status_code == 200
    assert listings_response.get_json()["listings"][0]["scores"]["object_score"] > 0
    assert listings_response.get_json()["total_count"] == 200
    assert len(districts_response.get_json()["districts"]) == 8
    assert districts_response.get_json()["districts"]
    assert recommendations_response.get_json()["shortlist"]
    assert compare_response.get_json()["comparison"] is not None


def test_data_quality_page_renders_metrics(demo_db_path):
    app = create_app({"TESTING": True, "DB_PATH": str(demo_db_path)})
    client = app.test_client()

    response = client.get("/data-quality")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Качество данных" in html
    assert "Nominatim" in html
    assert "Fallback" in html
