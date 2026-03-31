from main.app import create_app


def test_index_page_renders_success_state_with_test_database(populated_db_path):
    app = create_app({"TESTING": True, "DB_PATH": str(populated_db_path)})
    client = app.test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Аналитика рынка недвижимости" in html
    assert "Данные успешно загружены" in html
    assert "Москва, проспект Мира, 12" in html
    assert "Москва, Комсомольский проспект, 21" in html


def test_index_page_renders_empty_state_for_empty_database(empty_db_path):
    app = create_app({"TESTING": True, "DB_PATH": str(empty_db_path)})
    client = app.test_client()

    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Данные пока отсутствуют" in html


def test_index_page_applies_post_filters(populated_db_path):
    app = create_app({"TESTING": True, "DB_PATH": str(populated_db_path)})
    client = app.test_client()

    response = client.post(
        "/",
        data={
            "price_min": "18000000",
            "price_max": "30000000",
            "rooms": "3",
            "district": "Хамовники",
            "chart_type": "table",
            "action": "apply_filters",
        },
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Найдено по фильтрам" in html
    assert "Москва, Комсомольский проспект, 21" in html
    assert "Москва, проспект Мира, 12" not in html
