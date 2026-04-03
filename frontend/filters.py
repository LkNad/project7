# frontend/filters.py
from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from backend.config import DEFAULT_DB_PATH, resolve_path
from backend.Listing import Listing
from backend.queries import SELECT_ALL_DISTRICTS, SELECT_ALL_LISTINGS
from backend.scoring.engine import enrich_listings
from frontend.html_renderer import build_chart_context, build_compare_context, build_listing_cards_context, build_map_context


SOURCE_TRUST_MAP = {
    "cian": (88, "Крупный маркетплейс, обычно высокая полнота карточки"),
    "avito": (74, "Массовый источник, полезен для охвата, но требует ручной проверки"),
    "yandex": (72, "Нормальный агрегированный источник, доверять после ручной проверки"),
    "sample_data": (66, "Локально загруженный набор для аналитики и UX-проверок"),
}


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
    "preset": None,
    "score_weights": {
        "value": 0.30,
        "transport": 0.25,
        "infra": 0.20,
        "fit": 0.15,
        "district_bonus": 0.10,
    },
    "district_score_weights": {
        "object": 0.35,
        "transport": 0.20,
        "infra": 0.20,
        "family": 0.15,
        "investment": 0.10,
    },
}

SUPPORTED_CHART_TYPES = {"bar", "pie"}
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
        parsed = int(str(value).replace(" ", "").replace("\u00a0", ""))
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


def _normalize_weight_map(raw_values, defaults):
    normalized = {}
    for key, default in defaults.items():
        try:
            value = float(raw_values.get(key, default)) if raw_values else float(default)
        except (TypeError, ValueError):
            value = float(default)
        normalized[key] = max(value, 0.0)
    total = sum(normalized.values()) or sum(defaults.values()) or 1.0
    return {key: normalized[key] / total for key in normalized}


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


def _source_signature(item):
    source = str(item.get("source") or item.get("url") or "").lower()
    for key in SOURCE_TRUST_MAP:
        if key in source:
            return key
    return "sample_data"


def _dedupe_signature(item):
    address = " ".join(str(item.get("address") or "").lower().split())
    district = " ".join(str(item.get("district") or "").lower().split())
    price = round(float(item.get("price") or 0), -4)
    rooms = int(item.get("rooms") or 0)
    return address, district, price, rooms


def _dedupe_and_enrich_sources(listings):
    groups = {}
    for item in listings:
        groups.setdefault(_dedupe_signature(item), []).append(dict(item))

    result = []
    for group in groups.values():
        group = sorted(
            group,
            key=lambda item: (
                -SOURCE_TRUST_MAP.get(_source_signature(item), (60, ""))[0],
                -(1 if item.get("image_url") else 0),
                -(1 if item.get("description") else 0),
                str(item.get("created_at") or ""),
            ),
            reverse=False,
        )
        canonical = group[0]
        source_key = _source_signature(canonical)
        trust_score, trust_note = SOURCE_TRUST_MAP.get(source_key, (60, "Источник требует ручной проверки"))
        canonical["duplicate_count"] = len(group)
        canonical["source_trust_score"] = trust_score
        canonical["source_trust_note"] = trust_note
        canonical["source_label"] = source_key
        canonical["is_dedup_canonical"] = True
        result.append(canonical)

    return result


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

    return _dedupe_and_enrich_sources([Listing.from_row(row).to_dict() for row in rows]), None


def load_raw_data_from_db(db_path=None):
    normalized_path = _normalize_db_path(db_path)
    if not os.path.exists(normalized_path):
        return []
    try:
        conn = sqlite3.connect(normalized_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(SELECT_ALL_LISTINGS).fetchall()
        conn.close()
    except sqlite3.Error:
        return []
    return [Listing.from_row(row).to_dict() for row in rows]


def load_price_snapshots_from_db(db_path=None, snapshot_key=None):
    normalized_path = _normalize_db_path(db_path)
    if not os.path.exists(normalized_path) or not snapshot_key:
        return []
    try:
        conn = sqlite3.connect(normalized_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT snapshot_key, address, district, price, source, captured_at FROM listing_price_snapshots WHERE snapshot_key = ? ORDER BY captured_at ASC, id ASC",
            (snapshot_key,),
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        return []
    return [dict(row) for row in rows]


def load_districts_from_db(db_path=None):
    normalized_path = _normalize_db_path(db_path)
    if not os.path.exists(normalized_path):
        return []
    try:
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


def normalize_filters(form=None, user_weights=None):
    base_defaults = DEFAULT_FILTERS.copy()
    base_defaults["score_weights"] = _normalize_weight_map((user_weights or {}).get("score_weights"), DEFAULT_FILTERS["score_weights"])
    base_defaults["district_score_weights"] = _normalize_weight_map((user_weights or {}).get("district_score_weights"), DEFAULT_FILTERS["district_score_weights"])
    if not form:
        return base_defaults
    action = form.get("action")
    if action == "reset_filters":
        return base_defaults

    price_min = _coerce_price(form.get("price_min"), DEFAULT_FILTERS["price_range"][0])
    price_max = _coerce_price(form.get("price_max"), DEFAULT_FILTERS["price_range"][1])
    if price_min > price_max:
        price_min, price_max = price_max, price_min

    chart_type = form.get("chart_type") or base_defaults["chart_type"]
    if chart_type not in SUPPORTED_CHART_TYPES:
        chart_type = base_defaults["chart_type"]

    map_mode = form.get("map_mode") or base_defaults["map_mode"]
    if map_mode not in SUPPORTED_MAP_MODES:
        map_mode = base_defaults["map_mode"]

    compare_districts = form.getlist("compare_districts") if hasattr(form, "getlist") else form.get("compare_districts", [])
    if isinstance(compare_districts, str):
        compare_districts = [compare_districts]
    preset = (form.get("preset") or "").strip() or None

    normalized = {
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
        "preset": preset,
        "score_weights": base_defaults["score_weights"],
        "district_score_weights": base_defaults["district_score_weights"],
    }

    if preset == "family-ready":
        normalized["family_friendly_only"] = True
        normalized["map_mode"] = "family"
        normalized["shortlist_focus"] = "family"
        normalized["min_object_score"] = max(normalized["min_object_score"], 70)
    elif preset == "value-deals":
        normalized["undervalued_only"] = True
        normalized["map_mode"] = "value"
        normalized["shortlist_focus"] = "value"
        normalized["chart_type"] = "bar"
    elif preset == "fast-metro":
        normalized["transport_priority_only"] = True
        normalized["map_mode"] = "transport"
        normalized["max_metro_time"] = min(normalized["max_metro_time"] or 12, 12)
    elif preset == "balanced-top":
        normalized["map_mode"] = "overall"
        normalized["shortlist_focus"] = "top"
        normalized["min_object_score"] = max(normalized["min_object_score"], 65)

    if preset == "family-ready":
        normalized["score_weights"] = _normalize_weight_map({"value": 0.20, "transport": 0.20, "infra": 0.20, "fit": 0.10, "district_bonus": 0.30}, DEFAULT_FILTERS["score_weights"])
        normalized["district_score_weights"] = _normalize_weight_map({"object": 0.25, "transport": 0.15, "infra": 0.20, "family": 0.30, "investment": 0.10}, DEFAULT_FILTERS["district_score_weights"])
    elif preset == "value-deals":
        normalized["score_weights"] = _normalize_weight_map({"value": 0.40, "transport": 0.20, "infra": 0.15, "fit": 0.15, "district_bonus": 0.10}, DEFAULT_FILTERS["score_weights"])
        normalized["district_score_weights"] = _normalize_weight_map({"object": 0.25, "transport": 0.15, "infra": 0.15, "family": 0.05, "investment": 0.40}, DEFAULT_FILTERS["district_score_weights"])
    elif preset == "fast-metro":
        normalized["score_weights"] = _normalize_weight_map({"value": 0.18, "transport": 0.40, "infra": 0.18, "fit": 0.14, "district_bonus": 0.10}, DEFAULT_FILTERS["score_weights"])
        normalized["district_score_weights"] = _normalize_weight_map({"object": 0.25, "transport": 0.35, "infra": 0.20, "family": 0.10, "investment": 0.10}, DEFAULT_FILTERS["district_score_weights"])

    return normalized


def _listing_primary_score_key(filters):
    return {
        "overall": "object_score",
        "family": "family_score",
        "investment": "investment_score",
        "transport": "transport_score",
        "value": "value_score",
    }.get((filters or {}).get("map_mode"), "object_score")


def _listing_sort_key(item, filters=None):
    filters = filters or {}
    scores = item.get("scores", {})
    primary_key = _listing_primary_score_key(filters)
    primary_score = float(scores.get(primary_key, 0) or 0)
    overall_score = float(scores.get("object_score", 0) or 0)
    value_score = float(scores.get("value_score", 0) or 0)
    fit_score = float(scores.get("fit_score", 0) or 0)
    quality_signal = float(scores.get("quality_signal", 0) or 0)
    price = float(item.get("price", 0) or 0)
    return (-primary_score, -overall_score, -value_score, -fit_score, -quality_signal, price)


def filter_listings(listings, filters=None):
    filters = filters or DEFAULT_FILTERS
    price_min, price_max = filters["price_range"]
    filtered = []

    for item in listings:
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

    return sorted(filtered, key=lambda item: _listing_sort_key(item, filters))


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
        "presets": [
            {"value": "balanced-top", "label": "Сбалансированно"},
            {"value": "family-ready", "label": "Для семьи"},
            {"value": "value-deals", "label": "Value"},
            {"value": "fast-metro", "label": "Быстро до метро"},
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


def _build_data_quality(all_listings, filtered_listings):
    dataset = filtered_listings or all_listings
    latest_created_at = max((item.get("created_at") for item in all_listings if item.get("created_at")), default=None)
    latest_label = "нет даты"
    if latest_created_at:
        try:
            latest_label = datetime.fromisoformat(str(latest_created_at)).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            latest_label = str(latest_created_at)
    exact_geo = sum(1 for item in dataset if (item.get("geocode_source") or "").lower() == "nominatim")
    fallback_geo = sum(1 for item in dataset if (item.get("geocode_source") or "").lower() == "deterministic-local")
    return {
        "total": len(all_listings),
        "filtered": len(filtered_listings),
        "coverage_percent": round((len(filtered_listings) / len(all_listings)) * 100, 1) if all_listings else 0,
        "exact_geo": exact_geo,
        "fallback_geo": fallback_geo,
        "latest_label": latest_label,
        "source_count": len({item.get("source") for item in all_listings if item.get("source")}),
        "note": "Точные координаты используются там, где geocoder подтвердил адрес. Остальные точки помечаются как fallback.",
    }


def _build_price_history(raw_listings, listing):
    if not listing:
        return []
    target_signature = _dedupe_signature(listing)
    history = [item for item in raw_listings if _dedupe_signature(item) == target_signature and item.get("created_at")]
    history = sorted(history, key=lambda item: str(item.get("created_at") or ""))
    compact = []
    seen = set()
    for item in history:
        key = (item.get("created_at"), round(float(item.get("price") or 0), 0))
        if key in seen:
            continue
        seen.add(key)
        compact.append({
            "created_at": item.get("created_at"),
            "price": item.get("price", 0),
        })
    return compact[-8:]


def _build_price_history_summary(price_history):
    if len(price_history) < 2:
        return {"has_history": False, "delta": 0, "delta_percent": 0, "trend": "stable"}
    first = float(price_history[0].get("price") or 0)
    last = float(price_history[-1].get("price") or 0)
    delta = last - first
    delta_percent = round((delta / first) * 100, 1) if first else 0
    trend = "up" if delta > 0 else "down" if delta < 0 else "stable"
    max_price = max(float(item.get("price") or 0) for item in price_history) or 1
    points = []
    count = len(price_history)
    denominator = count - 1 if count > 1 else 1
    for index, item in enumerate(price_history):
        price = float(item.get("price") or 0)
        x = round((index * 100) / denominator, 2)
        y = round(100 - (price / max_price) * 100, 2)
        points.append({
            "x": x,
            "y": y,
            "label": item.get("created_at"),
            "price": price,
            "delta": round(price - float(price_history[index - 1].get("price") or 0), 0) if index > 0 else 0,
        })
    return {
        "has_history": True,
        "delta": round(delta, 0),
        "delta_percent": delta_percent,
        "trend": trend,
        "points": points,
    }


def _build_district_ranking_explainer(district):
    if not district:
        return []
    weights = district.get("score_weights") or {
        "object": 0.35,
        "transport": 0.20,
        "infra": 0.20,
        "family": 0.15,
        "investment": 0.10,
    }
    parts = {
        "Объекты": float(district.get("object_score") or 0) * float(weights.get("object", 0.35)),
        "Транспорт": float(district.get("transport_score") or 0) * float(weights.get("transport", 0.20)),
        "Инфраструктура": float(district.get("infra_score") or 0) * float(weights.get("infra", 0.20)),
        "Семья": float(district.get("family_score") or 0) * float(weights.get("family", 0.15)),
        "Инвестиции": float(district.get("investment_score") or 0) * float(weights.get("investment", 0.10)),
    }
    total = sum(parts.values()) or 1
    ordered = sorted(parts.items(), key=lambda item: item[1], reverse=True)
    return [
        {"label": label, "value": round(value, 1), "share": round((value / total) * 100)}
        for label, value in ordered
    ]


def build_listing_detail_context(listing_id, db_path=None, form=None, user_weights=None):
    all_listings, load_error = load_data_from_db(db_path=db_path)
    current_filters = normalize_filters(form, user_weights=user_weights)
    enriched_listings, computed_districts, recommendations = enrich_listings(all_listings, current_filters)
    districts = load_districts_from_db(db_path=db_path) or computed_districts
    listing = next((item for item in enriched_listings if item.get("id") == listing_id), None)
    listing_cards = build_listing_cards_context([listing] if listing else [])
    detailed_listing = listing_cards["items"][0] if listing_cards["items"] else None
    district = next((item for item in districts if detailed_listing and item.get("district") == detailed_listing.get("district")), None)
    similar = []
    if detailed_listing:
        same_district = [item for item in enriched_listings if item.get("district") == detailed_listing.get("district") and item.get("id") != listing_id]
        similar = build_listing_cards_context(sorted(
            same_district,
            key=lambda item: (
                abs((item.get("price") or 0) - (detailed_listing.get("price") or 0)),
                -item.get("scores", {}).get("object_score", 0),
            ),
        )[:3])["items"]
    snapshot_key = _dedupe_signature(detailed_listing) if detailed_listing else None
    raw_snapshots = load_price_snapshots_from_db(db_path=db_path, snapshot_key=snapshot_key)
    price_history = [
        {"created_at": item.get("captured_at"), "price": item.get("price", 0)}
        for item in raw_snapshots
    ] if raw_snapshots else _build_price_history(load_raw_data_from_db(db_path=db_path), detailed_listing)
    return {
        "listing": detailed_listing,
        "district": district,
        "similar": similar,
        "price_history": price_history,
        "price_history_summary": _build_price_history_summary(price_history),
        "data_quality": _build_data_quality(all_listings, enriched_listings),
        "load_error": load_error,
        "page_title": detailed_listing.get("title") if detailed_listing else "Карточка объекта",
        "current_filters": current_filters,
        "recommendations": recommendations,
    }


def build_district_detail_context(district_name, db_path=None, form=None, user_weights=None):
    all_listings, load_error = load_data_from_db(db_path=db_path)
    current_filters = normalize_filters(form, user_weights=user_weights)
    enriched_listings, computed_districts, recommendations = enrich_listings(all_listings, current_filters)
    districts = load_districts_from_db(db_path=db_path) or computed_districts
    district = next((item for item in districts if item.get("district") == district_name), None)
    district_listings = [item for item in enriched_listings if item.get("district") == district_name]
    shortlist = build_listing_cards_context(sorted(
        district_listings,
        key=lambda item: (-item.get("scores", {}).get("object_score", 0), item.get("price", 0)),
    )[:4])
    return {
        "district": district,
        "listings": shortlist["items"],
        "ranking_explainer": _build_district_ranking_explainer(district),
        "data_quality": _build_data_quality(all_listings, district_listings),
        "load_error": load_error,
        "page_title": district_name,
        "recommendations": recommendations,
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


def build_page_context(form=None, db_path=None, user_weights=None):
    all_listings, load_error = load_data_from_db(db_path=db_path)
    current_filters = normalize_filters(form, user_weights=user_weights)
    focus_listing = _coerce_int(form.get("focus_listing"), None) if form else None
    enriched_listings, computed_districts, recommendations = enrich_listings(all_listings, current_filters)
    districts = load_districts_from_db(db_path=db_path) or computed_districts
    filter_options = get_filter_options(enriched_listings, districts)
    current_filters = _apply_default_price_bounds(current_filters, filter_options, form=form)
    enriched_listings, computed_districts, recommendations = enrich_listings(all_listings, current_filters)
    districts = load_districts_from_db(db_path=db_path) or computed_districts
    filtered_listings = filter_listings(enriched_listings, current_filters)
    filtered_districts = [district for district in districts if district["district_score"] >= current_filters["min_district_score"]]
    mode_key = _listing_primary_score_key(current_filters)
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

    selected_listing = next((item for item in filtered_listings if focus_listing is not None and item.get("id") == focus_listing), None)

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
        "map_context": build_map_context(filtered_listings, filtered_districts, current_filters["map_mode"], shortlist, selected_listing=selected_listing),
        "compare": build_compare_context(filtered_districts, current_filters["compare_districts"]),
        "shortlist": shortlist,
        "selected_listing": selected_listing,
        "data_quality": _build_data_quality(all_listings, filtered_listings),
        "recommendations": recommendations,
        "results_count": len(filtered_listings),
        "total_count": len(all_listings),
        "status": _build_status(load_error, all_listings, filtered_listings, filters_applied),
        "load_error": load_error,
        "page_title": "Карта выбора недвижимости",
    }
