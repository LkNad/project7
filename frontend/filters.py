# frontend/filters.py
import os
import sqlite3

from backend.config import DEFAULT_DB_PATH, resolve_path
from backend.Listing import Listing
from backend.queries import SELECT_ALL_LISTINGS
from frontend.html_renderer import build_chart_context, build_listing_cards_context


DEFAULT_FILTERS = {
    "price_range": [0, 1_000_000],
    "rooms": None,
    "district": None,
    "chart_type": "bar",
}

SUPPORTED_CHART_TYPES = {"bar", "pie", "line", "table"}


def _normalize_db_path(db_path=None):
    if db_path:
        return str(resolve_path(db_path))

    env_db_path = os.getenv("MEPHI_DB_PATH")
    if env_db_path:
        return str(resolve_path(env_db_path))

    return str(resolve_path(DEFAULT_DB_PATH))


def _coerce_price(value, fallback):
    try:
        if value in (None, ""):
            return fallback
        parsed = int(value)
        return max(parsed, 0)
    except (TypeError, ValueError):
        return fallback


def _normalize_rooms_filter(value):
    if value in (None, ""):
        return None

    value = str(value).strip()
    if value == "4+":
        return "4+"

    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return None


def _format_rooms_label(rooms):
    if rooms == 0:
        return "Студия / без комнат"
    if rooms >= 4:
        return "4+ комнаты"
    if rooms == 1:
        return "1 комната"
    return f"{rooms} комнаты"


def _build_status(load_error, all_listings, filtered_listings, filters_applied):
    if load_error:
        return {
            "kind": "error",
            "title": "Ошибка загрузки данных",
            "message": load_error,
        }

    if not all_listings:
        return {
            "kind": "empty",
            "title": "Данные пока отсутствуют",
            "message": "База подключена, но в ней ещё нет объявлений для отображения.",
        }

    if not filtered_listings and filters_applied:
        return {
            "kind": "filtered_empty",
            "title": "По выбранным фильтрам ничего не найдено",
            "message": "Измените диапазон цены, район или число комнат, чтобы увидеть объявления.",
        }

    return {
        "kind": "success",
        "title": "Данные успешно загружены",
        "message": f"Загружено объявлений: {len(all_listings)}. Под текущие фильтры подходит: {len(filtered_listings)}.",
    }


def load_data_from_db(db_path=None):
    normalized_path = _normalize_db_path(db_path)
    if not os.path.exists(normalized_path):
        return [], f"Файл базы данных не найден: {normalized_path}"

    try:
        conn = sqlite3.connect(normalized_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(SELECT_ALL_LISTINGS)
        rows = cur.fetchall()
        conn.close()
    except sqlite3.Error as exc:
        return [], f"Не удалось прочитать данные из БД: {exc}"

    return [Listing.from_row(row).to_dict() for row in rows], None


def normalize_filters(form=None):
    if not form:
        return DEFAULT_FILTERS.copy()

    action = form.get("action")
    if action == "reset_filters":
        return DEFAULT_FILTERS.copy()

    price_min = _coerce_price(form.get("price_min"), DEFAULT_FILTERS["price_range"][0])
    price_max = _coerce_price(form.get("price_max"), DEFAULT_FILTERS["price_range"][1])
    if price_min > price_max:
        price_min, price_max = price_max, price_min

    rooms = _normalize_rooms_filter(form.get("rooms"))
    district = (form.get("district") or "").strip() or None
    chart_type = form.get("chart_type") or DEFAULT_FILTERS["chart_type"]
    if chart_type not in SUPPORTED_CHART_TYPES:
        chart_type = DEFAULT_FILTERS["chart_type"]

    return {
        "price_range": [price_min, price_max],
        "rooms": rooms,
        "district": district,
        "chart_type": chart_type,
    }


def filter_listings(listings, filters=None):
    filters = filters or DEFAULT_FILTERS
    price_min, price_max = filters["price_range"]
    rooms = filters.get("rooms")
    district = filters.get("district")

    filtered = [
        item
        for item in sorted(listings, key=lambda item: item["price"], reverse=True)
        if price_min <= item["price"] <= price_max
        and (
            rooms is None
            or (rooms == "4+" and item["rooms"] >= 4)
            or (rooms != "4+" and item["rooms"] == rooms)
        )
        and (district is None or item["district"] == district)
    ]
    return filtered


def get_filter_options(listings):
    districts = sorted({item["district"] for item in listings if item["district"]})
    rooms = sorted({item["rooms"] for item in listings if item["rooms"] is not None})
    prices = [item["price"] for item in listings if item["price"] is not None and item["price"] >= 0]

    room_options = []
    for room in [room for room in rooms if room < 4]:
        room_options.append({"value": str(room), "label": _format_rooms_label(room)})
    if any(room >= 4 for room in rooms):
        room_options.append({"value": "4+", "label": _format_rooms_label(4)})

    return {
        "districts": districts,
        "rooms": room_options,
        "price_bounds": {
            "min": int(min(prices)) if prices else DEFAULT_FILTERS["price_range"][0],
            "max": int(max(prices)) if prices else DEFAULT_FILTERS["price_range"][1],
        },
    }


def build_summary(listings):
    prices = [item["price"] for item in listings if item["price"] > 0]
    return {
        "count": len(listings),
        "min_price": min(prices) if prices else 0,
        "max_price": max(prices) if prices else 0,
        "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
    }


def _apply_default_price_bounds(filters, filter_options, form=None):
    if filters["price_range"] != DEFAULT_FILTERS["price_range"]:
        return filters

    action = form.get("action") if form else None
    if form and action not in (None, "reset_filters"):
        return filters

    adjusted = filters.copy()
    adjusted["price_range"] = [
        filter_options["price_bounds"]["min"],
        filter_options["price_bounds"]["max"],
    ]
    return adjusted


def build_page_context(form=None, db_path=None):
    all_listings, load_error = load_data_from_db(db_path=db_path)
    current_filters = normalize_filters(form)
    filter_options = get_filter_options(all_listings)
    current_filters = _apply_default_price_bounds(current_filters, filter_options, form=form)
    filtered_listings = filter_listings(all_listings, current_filters)

    filters_applied = bool(
        current_filters["district"]
        or current_filters["rooms"] is not None
        or current_filters["price_range"] != DEFAULT_FILTERS["price_range"]
    )

    return {
        "current_filters": current_filters,
        "filter_options": filter_options,
        "listings": filtered_listings,
        "summary": build_summary(filtered_listings),
        "chart": build_chart_context(filtered_listings, current_filters["chart_type"]),
        "listing_cards": build_listing_cards_context(filtered_listings),
        "results_count": len(filtered_listings),
        "total_count": len(all_listings),
        "status": _build_status(load_error, all_listings, filtered_listings, filters_applied),
        "load_error": load_error,
    }
