from backend.dataset_tools import CSV_FIELDNAMES, clean_rows, dataset_quality_stats, headers_are_compatible, merge_rows


def test_headers_are_compatible_for_project_and_external_csv():
    assert headers_are_compatible(CSV_FIELDNAMES)
    assert headers_are_compatible(
        [
            "listing_id",
            "title",
            "addres",
            "district",
            "price",
            "area",
            "rooms",
            "source_url",
        ]
    )
    assert not headers_are_compatible(["title", "district", "source_url"])


def test_clean_rows_drops_incomplete_rows_and_deduplicates_by_source_url():
    rows = [
        {
            "id": "0",
            "title": "A",
            "addres": "Москва, ул. Первая, 1",
            "district": "Тверской",
            "price": "10000000",
            "area": "40",
            "source_url": "https://example.test/1",
        },
        {
            "id": "1",
            "title": "B",
            "addres": "Москва, ул. Вторая, 2",
            "district": "Тверской",
            "price": "",
            "area": "50",
            "source_url": "https://example.test/2",
        },
        {
            "id": "2",
            "title": "C",
            "addres": "Москва, ул. Третья, 3",
            "district": "Арбат",
            "price": "20000000",
            "area": "60",
            "source_url": "https://example.test/1",
        },
    ]

    cleaned = clean_rows(rows)

    assert len(cleaned) == 1
    assert cleaned[0]["id"] == "0"
    assert cleaned[0]["source_url"] == "https://example.test/1"


def test_merge_rows_keeps_only_clean_unique_rows():
    base_rows = [
        {
            "id": "0",
            "title": "Base",
            "addres": "Москва, ул. Базовая, 1",
            "district": "Хамовники",
            "price": "15000000",
            "area": "45",
            "rooms": "1",
            "source_url": "https://example.test/base-1",
        }
    ]
    extra_rows = [
        {
            "listing_id": "10",
            "title": "Extra",
            "addres": "Москва, ул. Новая, 2",
            "district": "Пресненский",
            "price": "25000000",
            "area": "70",
            "rooms": "2",
            "source_url": "https://example.test/extra-1",
        },
        {
            "listing_id": "11",
            "title": "Duplicate",
            "addres": "Москва, ул. Базовая, 1",
            "district": "Хамовники",
            "price": "15000000",
            "area": "45",
            "rooms": "1",
            "source_url": "https://example.test/base-1",
        },
    ]

    merged = merge_rows(base_rows, extra_rows)

    assert len(merged) == 2
    assert [row["id"] for row in merged] == ["0", "1"]
    assert {row["source_url"] for row in merged} == {
        "https://example.test/base-1",
        "https://example.test/extra-1",
    }


def test_dataset_quality_stats_counts_dropped_rows():
    rows = [
        {"title": "A", "addres": "Москва, ул. Первая, 1", "district": "Тверской", "price": "1", "area": "10", "source_url": "https://example.test/1"},
        {"title": "B", "addres": "Москва, ул. Вторая, 2", "district": "Тверской", "price": "", "area": "10", "source_url": "https://example.test/2"},
        {"title": "C", "addres": "Москва, ул. Третья, 3", "district": "Тверской", "price": "1", "area": "10", "source_url": "https://example.test/1"},
    ]

    stats = dataset_quality_stats(rows)

    assert stats == {
        "raw_rows": 3,
        "valid_rows": 1,
        "incomplete_rows": 1,
        "duplicate_rows": 1,
        "dropped_rows": 2,
    }
