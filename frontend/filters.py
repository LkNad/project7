# frontend/filters.py
from __future__ import annotations

import os
import sqlite3

from backend.config import DEFAULT_DB_PATH, resolve_path
from backend.Listing import Listing
from backend.queries import SELECT_ALL_DISTRICTS, SELECT_ALL_LISTINGS
from backend.scoring.engine import enrich_listings
from backend.DataFetcher import DataFetcher
from frontend.html_renderer import build_chart_context, build_compare_context, build_listing_cards_context, build_map_context


DEFAULT_FILTERS = {
    "price_range": [0, 1_000_000],
    "rooms": None,
    "district": None,
    "chart_type": "bar",
    "map_mode": "overall",
    "area_min": 0,
    "deal_type": None,
    "max_metro_time": None,
    "min_district_score": 0,
    "min_object_score": 0,
    "undervalued_only": False,
    "family_friendly_only": False,
    "investment_friendly_only": False,
    "transport_priority_only": False,
    "compare_districts": [],
    "shortlist_focus": "top",
}

SUPPORTED_CHART_TYPES = {"bar", "pie", "line", "table"}
SUPPORTED_MAP_MODES = {"overall", "family", "investment", "transport", "value"}


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


def _coerce_int(value, fallback=None):
    try:
        if value in (None, ""):
            return fallback
        return max(int(value), 0)
    except (TypeError, ValueError):
        return fallback


def _coerce_bool(value):
    return str(value).lower() in {"1", "true", "on", "yes"}


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
        return {"kind": "error", "title": "Ошибка загрузки данных", "message": load_error}
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
            "message": "Измените бюджет, район, score или транспортные ограничения, чтобы увидеть объявления.",
        }
    return {
        "kind": "success",
        "title": "Витрина рекомендаций готова",
        "message": f"В базе {len(all_listings)} объявлений. Под текущий сценарий подходит {len(filtered_listings)}.",
    }


def load_data_from_db(db_path=None):
    normalized_path = _normalize_db_path(db_path)
    if not os.path.exists(normalized_path):
        return [], f"Файл базы данных не найден: {normalized_path}"

    try:
        DataFetcher(db_path=normalized_path).ensure_database_compatibility()
        conn = sqlite3.connect(normalized_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(SELECT_ALL_LISTINGS)
        rows = cur.fetchall()
        conn.close()
    except sqlite3.Error as exc:
        return [], f"Не удалось прочитать данные из БД: {exc}"

    return [Listing.from_row(row).to_dict() for row in rows], None


def load_districts_from_db(db_path=None):
    normalized_path = _normalize_db_path(db_path)
    if not os.path.exists(normalized_path):
        return []
    try:
        DataFetcher(db_path=normalized_path).ensure_database_compatibility()
        conn = sqlite3.connect(normalized_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(SELECT_ALL_DISTRICTS).fetchall()
        conn.close()
    except sqlite3.Error:
        return []

    districts = []
    for row in rows:
        item = dict(row)
        item["highlights"] = [part.strip() for part in (item.get("highlights") or "").split(";") if part.strip()]
        districts.append(item)
    return districts


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

    chart_type = form.get("chart_type") or DEFAULT_FILTERS["chart_type"]
    if chart_type not in SUPPORTED_CHART_TYPES:
        chart_type = DEFAULT_FILTERS["chart_type"]

    map_mode = form.get("map_mode") or DEFAULT_FILTERS["map_mode"]
    if map_mode not in SUPPORTED_MAP_MODES:
        map_mode = DEFAULT_FILTERS["map_mode"]

    compare_districts = form.getlist("compare_districts") if hasattr(form, "getlist") else form.get("compare_districts", [])
    if isinstance(compare_districts, str):
        compare_districts = [compare_districts]

    return {
        "price_range": [price_min, price_max],
        "rooms": _normalize_rooms_filter(form.get("rooms")),
        "district": (form.get("district") or "").strip() or None,
        "chart_type": chart_type,
        "map_mode": map_mode,
        "area_min": _coerce_int(form.get("area_min"), 0) or 0,
        "deal_type": (form.get("deal_type") or "").strip() or None,
        "max_metro_time": _coerce_int(form.get("max_metro_time"), None),
        "min_district_score": _coerce_int(form.get("min_district_score"), 0) or 0,
        "min_object_score": _coerce_int(form.get("min_object_score"), 0) or 0,
        "undervalued_only": _coerce_bool(form.get("undervalued_only")),
        "family_friendly_only": _coerce_bool(form.get("family_friendly_only")),
        "investment_friendly_only": _coerce_bool(form.get("investment_friendly_only")),
        "transport_priority_only": _coerce_bool(form.get("transport_priority_only")),
        "compare_districts": compare_districts[:2],
        "shortlist_focus": (form.get("shortlist_focus") or "top").strip() or "top",
    }


def filter_listings(listings, filters=None):
    filters = filters or DEFAULT_FILTERS
    price_min, price_max = filters["price_range"]
    filtered = []

    for item in sorted(listings, key=lambda listing: listing["price"], reverse=True):
        if not (price_min <= item["price"] <= price_max):
            continue
        if filters.get("rooms") is not None:
            rooms_filter = filters["rooms"]
            if rooms_filter == "4+" and item["rooms"] < 4:
                continue
            if rooms_filter != "4+" and item["rooms"] != rooms_filter:
                continue
        if filters.get("district") and item["district"] != filters["district"]:
            continue
        if item.get("area", 0) < filters.get("area_min", 0):
            continue
        if filters.get("deal_type") and item.get("deal_type") != filters["deal_type"]:
            continue
        if filters.get("max_metro_time") is not None and (item.get("metro_time_min") or 10**9) > filters["max_metro_time"]:
            continue
        if item.get("district_score", 0) < filters.get("min_district_score", 0):
            continue
        if item.get("scores", {}).get("object_score", 0) < filters.get("min_object_score", 0):
            continue
        if filters.get("undervalued_only") and item.get("scores", {}).get("value_score", 0) < 70:
            continue
        if filters.get("family_friendly_only") and item.get("scores", {}).get("family_score", 0) < 75:
            continue
        if filters.get("investment_friendly_only") and item.get("scores", {}).get("investment_score", 0) < 75:
            continue
        if filters.get("transport_priority_only") and item.get("scores", {}).get("transport_score", 0) < 75:
            continue
        filtered.append(item)

    return filtered


def get_filter_options(listings, districts=None):
    districts = districts or []
    district_names = sorted({item["district"] for item in listings if item["district"]})
    rooms = sorted({item["rooms"] for item in listings if item["rooms"] is not None})
    prices = [item["price"] for item in listings if item["price"] is not None and item["price"] >= 0]
    metro_times = [item.get("metro_time_min") for item in listings if item.get("metro_time_min") is not None]
    areas = [item.get("area") for item in listings if item.get("area") is not None]

    room_options = []
    for room in [room for room in rooms if room < 4]:
        room_options.append({"value": str(room), "label": _format_rooms_label(room)})
    if any(room >= 4 for room in rooms):
        room_options.append({"value": "4+", "label": _format_rooms_label(4)})

    return {
        "districts": district_names,
        "rooms": room_options,
        "price_bounds": {
            "min": int(min(prices)) if prices else DEFAULT_FILTERS["price_range"][0],
            "max": int(max(prices)) if prices else DEFAULT_FILTERS["price_range"][1],
        },
        "metro_bounds": {"min": int(min(metro_times)) if metro_times else 0, "max": int(max(metro_times)) if metro_times else 30},
        "area_bounds": {"min": int(min(areas)) if areas else 0, "max": int(max(areas)) if areas else 200},
        "district_compare_options": [item["district"] for item in districts],
        "map_modes": [
            {"value": "overall", "label": "Общий рейтинг"},
            {"value": "family", "label": "Для семьи"},
            {"value": "investment", "label": "Для инвестиций"},
            {"value": "transport", "label": "Транспорт"},
            {"value": "value", "label": "Цена / качество"},
        ],
        "shortlist_focus": [
            {"value": "top", "label": "Топ-подборка"},
            {"value": "value", "label": "Цена / качество"},
            {"value": "family", "label": "Семья"},
        ],
    }


def build_summary(listings):
    prices = [item["price"] for item in listings if item["price"] > 0]
    object_scores = [item.get("scores", {}).get("object_score", 0) for item in listings]
    district_scores = [item.get("district_score", 0) for item in listings]
    return {
        "count": len(listings),
        "min_price": min(prices) if prices else 0,
        "max_price": max(prices) if prices else 0,
        "avg_price": round(sum(prices) / len(prices), 2) if prices else 0,
        "avg_object_score": round(sum(object_scores) / len(object_scores), 2) if object_scores else 0,
        "avg_district_score": round(sum(district_scores) / len(district_scores), 2) if district_scores else 0,
    }


def _apply_default_price_bounds(filters, filter_options, form=None):
    if filters["price_range"] != DEFAULT_FILTERS["price_range"]:
        return filters
    action = form.get("action") if form else None
    if form and action not in (None, "reset_filters"):
        return filters
    adjusted = filters.copy()
    adjusted["price_range"] = [filter_options["price_bounds"]["min"], filter_options["price_bounds"]["max"]]
    return adjusted


def build_page_context(form=None, db_path=None):
    all_listings, load_error = load_data_from_db(db_path=db_path)
    current_filters = normalize_filters(form)
    enriched_listings, computed_districts, recommendations = enrich_listings(all_listings, current_filters)
    districts = load_districts_from_db(db_path=db_path) or computed_districts
    filter_options = get_filter_options(enriched_listings, districts)
    current_filters = _apply_default_price_bounds(current_filters, filter_options, form=form)
    enriched_listings, computed_districts, recommendations = enrich_listings(all_listings, current_filters)
    districts = load_districts_from_db(db_path=db_path) or computed_districts
    filtered_listings = filter_listings(enriched_listings, current_filters)
    filtered_districts = [district for district in districts if district["district_score"] >= current_filters["min_district_score"]]
    mode_key = {
        "overall": "object_score",
        "family": "family_score",
        "investment": "investment_score",
        "transport": "transport_score",
        "value": "value_score",
    }.get(current_filters["map_mode"], "object_score")
    shortlist = sorted(
        filtered_listings,
        key=lambda item: (
            -(item.get("scores", {}).get(mode_key, 0)),
            -(item.get("scores", {}).get("object_score", 0)),
            item.get("price", 0),
        ),
    )[:4]

    if current_filters.get("shortlist_focus") == "value":
        shortlist = sorted(filtered_listings, key=lambda item: (-item.get("scores", {}).get("value_score", 0), item.get("price", 0)))[:4]
    elif current_filters.get("shortlist_focus") == "family":
        shortlist = sorted(filtered_listings, key=lambda item: (-item.get("scores", {}).get("family_score", 0), -item.get("scores", {}).get("object_score", 0), item.get("price", 0)))[:4]

    filters_applied = bool(
        current_filters["district"]
        or current_filters["rooms"] is not None
        or current_filters["price_range"] != DEFAULT_FILTERS["price_range"]
        or current_filters["area_min"]
        or current_filters["deal_type"]
        or current_filters["max_metro_time"] is not None
        or current_filters["min_district_score"]
        or current_filters["min_object_score"]
        or current_filters["undervalued_only"]
        or current_filters["family_friendly_only"]
        or current_filters["investment_friendly_only"]
        or current_filters["transport_priority_only"]
    )

    return {
        "current_filters": current_filters,
        "filter_options": filter_options,
        "listings": filtered_listings,
        "districts": filtered_districts,
        "summary": build_summary(filtered_listings),
        "chart": build_chart_context(filtered_listings, current_filters["chart_type"]),
        "listing_cards": build_listing_cards_context(filtered_listings),
        "map_context": build_map_context(filtered_listings, filtered_districts, current_filters["map_mode"], shortlist),
        "compare": build_compare_context(filtered_districts, current_filters["compare_districts"]),
        "shortlist": shortlist,
        "recommendations": recommendations,
        "results_count": len(filtered_listings),
        "total_count": len(all_listings),
        "status": _build_status(load_error, all_listings, filtered_listings, filters_applied),
        "load_error": load_error,
        "page_title": "Карта выбора недвижимости",
    }
