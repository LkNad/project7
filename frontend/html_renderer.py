# frontend/html_renderer.py
import json
import math
import re
from pathlib import Path
from datetime import datetime, timezone


MAP_MODE_CONFIG = {
    "overall": {
        "label": "Общий рейтинг",
        "description": "Сбалансированный сценарий для выбора объекта с сильным сочетанием цены, района и повседневного комфорта.",
        "workspace_title": "Карта рыночного выбора",
        "workspace_subtitle": "Главный экран собирает сильные районы, shortlist и лучшие объекты в одном рабочем полотне.",
        "listing_score_key": "object_score",
        "district_score_key": "district_score",
        "accent": "#2563eb",
    },
    "family": {
        "label": "Для семьи",
        "description": "Фокус на семейной инфраструктуре, устойчивом районе и удобной повседневной жизни рядом с сервисами.",
        "workspace_title": "Семейная карта районов и просторных объектов",
        "workspace_subtitle": "Подсвечены районы с сильной инфраструктурой, площадью и устойчивым качеством жизни без визуального шума.",
        "listing_score_key": "family_score",
        "district_score_key": "family_score",
        "accent": "#0f766e",
    },
    "investment": {
        "label": "Для инвестиций",
        "description": "Сценарий выделяет ликвидность, инвестиционный потенциал и районы, где ценовой сигнал выглядит сильнее рынка.",
        "workspace_title": "Инвестиционная карта ликвидности и потенциала",
        "workspace_subtitle": "Фокус на ликвидных форматах, районах с сильным спросом и объектах ниже локальной медианы.",
        "listing_score_key": "investment_score",
        "district_score_key": "investment_score",
        "accent": "#7c3aed",
    },
    "transport": {
        "label": "Транспорт",
        "description": "Режим для поиска районов и объектов с лучшим временем в пути и транспортной доступностью.",
        "workspace_title": "Карта транспортной доступности и метро",
        "workspace_subtitle": "Показывает районы и объекты, где ежедневная мобильность выглядит максимально сильной и читаемой.",
        "listing_score_key": "transport_score",
        "district_score_key": "transport_score",
        "accent": "#ea580c",
    },
    "value": {
        "label": "Цена / качество",
        "description": "Режим показывает объекты со справедливой ценой и районы, где стоимость выглядит рациональной относительно качества.",
        "workspace_title": "Карта цены и качества",
        "workspace_subtitle": "Фокус на рациональных входах в рынок, сигналах справедливой цены и бюджетном балансе районов.",
        "listing_score_key": "value_score",
        "district_score_key": "budget_fit_score",
        "accent": "#059669",
    },
}


CHART_COLORS = [
    "#3b6cff",
    "#16a34a",
    "#f1b84b",
    "#0f766e",
    "#ea580c",
    "#5f88ff",
    "#7aa6c2",
    "#1f4cc7",
]

BASE_DIR = Path(__file__).resolve().parent.parent
DISTRICT_GEOJSON_PATH = BASE_DIR / "frontend" / "static" / "data" / "districts.geojson"
DISTRICT_NAME_ALIASES = {
    "бирюлево восточное": "бирюлево восточное",
    "медведково северное": "северное медведково",
    "теплый стан": "теплый стан",
    "хорошево-мневники": "хорошево-мневники",
    "хорошево мневники": "хорошево-мневники",
    "черемушки": "черемушки",
    "хорошевский": "хорошевский",
}
SIMPLIFY_TOLERANCE = 0.00045


ADDRESS_UNIT_RE = re.compile(
    r"(?:,?\s*(?:кв(?:артира)?|ап(?:артамент)?|пом(?:ещение)?|оф(?:ис)?|комн(?:ата)?|room)\.?\s*\d+[а-яa-z0-9/-]*)$",
    re.IGNORECASE,
)


def _normalize_map_address(address):
    cleaned = " ".join(str(address or "").split()).strip(" ,")
    cleaned = ADDRESS_UNIT_RE.sub("", cleaned)
    return cleaned.strip(" ,")


def _freshness_payload(created_at):
    if not created_at:
        return {"freshness_label": "без даты", "freshness_bucket": "unknown"}
    try:
        created_dt = datetime.fromisoformat(str(created_at))
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        age_hours = max((datetime.now(timezone.utc) - created_dt).total_seconds() / 3600, 0)
    except ValueError:
        return {"freshness_label": str(created_at), "freshness_bucket": "unknown"}

    if age_hours < 24:
        return {"freshness_label": f"{int(age_hours) or 1} ч назад", "freshness_bucket": "fresh"}
    age_days = age_hours / 24
    if age_days < 7:
        return {"freshness_label": f"{int(age_days)} д назад", "freshness_bucket": "recent"}
    if age_days < 30:
        return {"freshness_label": f"{int(age_days)} д назад", "freshness_bucket": "stale"}
    return {"freshness_label": f"{int(age_days // 30) or 1} мес назад", "freshness_bucket": "old"}


def _trust_band(score):
    if score >= 85:
        return "high"
    if score >= 70:
        return "mid"
    return "low"


def _geocode_quality_payload(item):
    geocode_source = str(item.get("geocode_source") or "").lower()
    geocode_confidence = float(item.get("geocode_confidence") or 0)
    if geocode_source == "nominatim":
        return {
            "geo_precision_label": "гео: address-level",
            "geo_precision_tone": "high",
            "geo_precision_note": f"Nominatim, confidence {geocode_confidence:.2f}",
        }
    if geocode_source == "yandex-maps":
        return {
            "geo_precision_label": "гео: address-level",
            "geo_precision_tone": "high",
            "geo_precision_note": f"Yandex Maps search, confidence {geocode_confidence:.2f}",
        }
    if geocode_source == "yandex-http":
        return {
            "geo_precision_label": "гео: address-level",
            "geo_precision_tone": "high",
            "geo_precision_note": f"Yandex HTTP geocoder, confidence {geocode_confidence:.2f}",
        }
    if geocode_source == "cian-page":
        return {
            "geo_precision_label": "гео: address-level",
            "geo_precision_tone": "high",
            "geo_precision_note": "Координаты извлечены из текущей страницы объявления",
        }
    if geocode_source in {"source-payload", "provided"}:
        return {
            "geo_precision_label": "гео: source payload",
            "geo_precision_tone": "mid",
            "geo_precision_note": "Координаты пришли из исходного источника",
        }
    if geocode_source == "deterministic-local":
        return {
            "geo_precision_label": "гео: fallback",
            "geo_precision_tone": "watch",
            "geo_precision_note": f"Локальная детерминированная точка, confidence {geocode_confidence:.2f}",
        }
    return {
        "geo_precision_label": "гео: unknown",
        "geo_precision_tone": "watch",
        "geo_precision_note": "Источник координат не подтвержден",
    }


def _normalize_district_name(name):
    normalized = " ".join(str(name or "").lower().replace("ё", "е").split()).strip().strip('"\'`')
    return DISTRICT_NAME_ALIASES.get(normalized, normalized)


def _point_line_distance(point, start, end):
    if start == end:
        return math.dist(point, start)
    numerator = abs(
        (end[1] - start[1]) * point[0]
        - (end[0] - start[0]) * point[1]
        + end[0] * start[1]
        - end[1] * start[0]
    )
    denominator = math.sqrt((end[1] - start[1]) ** 2 + (end[0] - start[0]) ** 2)
    return numerator / denominator if denominator else 0


def _simplify_ring(points, tolerance=SIMPLIFY_TOLERANCE):
    if len(points) <= 5:
        return points

    closed = points[0] == points[-1]
    working = points[:-1] if closed else points[:]
    if len(working) <= 3:
        return points

    def _rdp(segment):
        if len(segment) <= 2:
            return segment
        start = segment[0]
        end = segment[-1]
        max_distance = -1
        split_index = 0
        for index in range(1, len(segment) - 1):
            distance = _point_line_distance(segment[index], start, end)
            if distance > max_distance:
                max_distance = distance
                split_index = index
        if max_distance <= tolerance:
            return [start, end]
        left = _rdp(segment[: split_index + 1])
        right = _rdp(segment[split_index:])
        return left[:-1] + right

    simplified = _rdp(working)
    if len(simplified) < 4:
        return points
    if closed:
        simplified.append(simplified[0])
    return simplified


def _simplify_geometry(geometry):
    if not isinstance(geometry, dict):
        return geometry
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        return {
            "type": "Polygon",
            "coordinates": [_simplify_ring(ring) for ring in coordinates if isinstance(ring, list)],
        }
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        return {
            "type": "MultiPolygon",
            "coordinates": [
                [_simplify_ring(ring) for ring in polygon if isinstance(ring, list)]
                for polygon in coordinates
                if isinstance(polygon, list)
            ],
        }
    return geometry


def _geometry_to_multipolygon_coordinates(geometry):
    if not isinstance(geometry, dict):
        return []
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon" and isinstance(coordinates, list):
        return [coordinates]
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        return coordinates
    return []


def _merge_features_to_multipolygon(features):
    coordinates = []
    for feature in features:
        coordinates.extend(_geometry_to_multipolygon_coordinates((feature or {}).get("geometry")))
    if not coordinates:
        return None
    return {"type": "MultiPolygon", "coordinates": coordinates}


def _load_real_district_geojson():
    if not DISTRICT_GEOJSON_PATH.exists():
        return {}
    try:
        payload = json.loads(DISTRICT_GEOJSON_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        return {}

    feature_map = {}
    zelao_features = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        geometry = feature.get("geometry") or {}
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        if not geometry.get("coordinates"):
            continue
        props = feature.get("properties") or {}
        if _normalize_district_name(props.get("name_ao") or props.get("NAME_AO")) == "зеленоградский":
            zelao_features.append(feature)
        names = [
            props.get("source_name"),
            props.get("district"),
            props.get("name"),
            props.get("NAME"),
            props.get("adm_name"),
            props.get("official_name"),
        ]
        for name in names:
            normalized = _normalize_district_name(name)
            if normalized:
                feature_map[normalized] = feature
    zelao_geometry = _merge_features_to_multipolygon(zelao_features)
    if zelao_geometry:
        feature_map.setdefault(
            "зеленоград",
            {
                "type": "Feature",
                "geometry": zelao_geometry,
                "properties": {
                    "district": "Зеленоград",
                    "source_name": "Зеленоградский административный округ",
                    "name_ao": "Зеленоградский",
                    "abbrev_ao": "ЗелАО",
                    "type_mo": "Административный округ",
                },
            },
        )
    return feature_map


def _stable_hash(value):
    return sum((index + 1) * ord(char) for index, char in enumerate(str(value or "")))


def _display_coordinates(item):
    lat = item.get("lat")
    lon = item.get("lon")
    if lat in (None, 0, 0.0) or lon in (None, 0, 0.0):
        return lat, lon
    return round(lat, 6), round(lon, 6)


def _group_counts(data, key):
    grouped = {}
    for item in data:
        grouped[item[key]] = grouped.get(item[key], 0) + 1
    return grouped


def build_chart_context(data, chart_type="bar"):
    chart_type = chart_type or "bar"
    if chart_type == "pie":
        return build_pie_chart_context(data)
    return build_bar_chart_context(data)


def build_bar_chart_context(data):
    districts = _group_counts(data, "district")
    max_count = max(districts.values(), default=0)
    items = [
        {
            "label": district,
            "count": count,
            "width_percent": round((count / max_count) * 100, 2) if max_count else 0,
        }
        for district, count in sorted(districts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "type": "bar",
        "title": "Распределение объявлений по районам",
        "items": items,
        "empty_message": "Нет данных для отображения",
    }


def build_pie_chart_context(data):
    rooms_count = _group_counts(data, "rooms")
    if not rooms_count:
        return {
            "type": "pie",
            "title": "Распределение по количеству комнат",
            "segments": [],
            "legend": [],
            "empty_message": "Нет данных для отображения",
        }

    total = sum(rooms_count.values())
    current_angle = 0
    center_x, center_y = 100, 100
    radius = 80
    segments = []
    legend = []

    for index, (rooms, count) in enumerate(rooms_count.items()):
        percentage = count / total
        angle = percentage * 360
        color = CHART_COLORS[index % len(CHART_COLORS)]

        if angle == 360:
            path = None
        else:
            start_angle = current_angle
            end_angle = current_angle + angle
            start_rad = (start_angle - 90) * math.pi / 180
            end_rad = (end_angle - 90) * math.pi / 180
            start_x = center_x + radius * math.cos(start_rad)
            start_y = center_y + radius * math.sin(start_rad)
            end_x = center_x + radius * math.cos(end_rad)
            end_y = center_y + radius * math.sin(end_rad)
            large_arc_flag = 1 if angle > 180 else 0
            path = (
                f"M {center_x} {center_y} "
                f"L {start_x} {start_y} "
                f"A {radius} {radius} 0 {large_arc_flag} 1 {end_x} {end_y} Z"
            )

        segments.append(
            {
                "color": color,
                "path": path,
                "full_circle": angle == 360,
                "center_x": center_x,
                "center_y": center_y,
                "radius": radius,
            }
        )
        legend.append(
            {
                "label": f"{rooms} комн.",
                "count": count,
                "percentage": round(percentage * 100, 1),
                "color": color,
            }
        )
        current_angle += angle

    return {
        "type": "pie",
        "title": "Распределение по количеству комнат",
        "segments": segments,
        "legend": legend,
        "empty_message": "Нет данных для отображения",
    }


def build_listing_cards_context(data):
    prepared_items = []
    for index, item in enumerate(data, start=1):
        prepared = dict(item)
        reasons = [reason.strip() for reason in (prepared.get("recommendation_reasons") or []) if str(reason).strip()]
        score = round(prepared.get("scores", {}).get("object_score", prepared.get("object_score", 0)) or 0, 1)
        strengths = []
        caveats = []
        if prepared.get("scores", {}).get("transport_score", 0) >= 75:
            strengths.append("сильная транспортная доступность")
        if prepared.get("scores", {}).get("family_score", 0) >= 75:
            strengths.append("хороший семейный сценарий")
        if prepared.get("scores", {}).get("value_score", 0) >= 70:
            strengths.append("сильная цена/качество")
        metro_time = prepared.get("metro_time_min")
        if isinstance(metro_time, (int, float)) and metro_time > 18:
            caveats.append("метро не в пешем радиусе")
        if prepared.get("scores", {}).get("investment_score", 0) < 60:
            caveats.append("не самый сильный инвест-сценарий")
        if prepared.get("price_per_m2", 0) and prepared.get("scores", {}).get("value_score", 0) < 65:
            caveats.append("цена за м² выше комфортного сценария")
        completeness = 0
        for key in ("image_url", "metro_station", "description", "url"):
            if prepared.get(key):
                completeness += 1
        geocode_bonus = 14 if (prepared.get("geocode_source") or "").lower() in {"nominatim", "yandex-http", "cian-page"} else 7 if prepared.get("lat") and prepared.get("lon") else 0
        confidence_score = min(96, 52 + len(reasons) * 8 + completeness * 5 + geocode_bonus)
        score_parts = {
            "value": round((prepared.get("scores", {}).get("value_score", 0) * 0.30), 1),
            "transport": round((prepared.get("scores", {}).get("transport_score", 0) * 0.25), 1),
            "infra": round((prepared.get("scores", {}).get("infra_score", 0) * 0.20), 1),
            "fit": round((prepared.get("scores", {}).get("fit_score", 0) * 0.15), 1),
            "district_bonus": round((prepared.get("scores", {}).get("district_bonus", 0) * 0.10), 1),
        }
        total_parts = sum(score_parts.values()) or 1
        explain_parts = [
            {"key": "value", "label": "Цена / качество", "value": score_parts["value"], "share": round(score_parts["value"] / total_parts * 100), "weight": 30},
            {"key": "transport", "label": "Транспорт", "value": score_parts["transport"], "share": round(score_parts["transport"] / total_parts * 100), "weight": 25},
            {"key": "infra", "label": "Инфраструктура", "value": score_parts["infra"], "share": round(score_parts["infra"] / total_parts * 100), "weight": 20},
            {"key": "fit", "label": "Fit к фильтрам", "value": score_parts["fit"], "share": round(score_parts["fit"] / total_parts * 100), "weight": 15},
            {"key": "district_bonus", "label": "Сила района", "value": score_parts["district_bonus"], "share": round(score_parts["district_bonus"] / total_parts * 100), "weight": 10},
        ]
        prepared["recommendation_reasons"] = reasons
        prepared["price_compact"] = prepared.get("price_compact") or _format_price_compact(prepared.get("price", 0))
        prepared["marker_badge"] = prepared.get("marker_badge") or ("Топ" if index <= 5 else "Выбор")
        prepared["marker_note"] = prepared.get("marker_note") or f"Сценарий {score}/100"
        prepared["explain_summary"] = strengths[0] if strengths else f"сценарный score {score} поддерживает объект в shortlist"
        prepared["caveat"] = caveats[0] if caveats else "явных красных флагов по текущим фильтрам не видно"
        prepared["shortlist_rank"] = index if index <= 4 else None
        prepared["confidence_score"] = confidence_score
        prepared["confidence_note"] = "Собран из полноты карточки, качества геокодинга и числа подтверждающих сигналов."
        prepared["score_explainer"] = explain_parts
        prepared["score_penalties"] = caveats[:3]
        prepared.update(_freshness_payload(prepared.get("created_at")))
        prepared.update(_geocode_quality_payload(prepared))
        prepared["trust_band"] = _trust_band(prepared.get("source_trust_score", 60))
        prepared_items.append(prepared)
    return {
        "title": "Карта и карточки объектов",
        "items": prepared_items,
        "empty_message": "Нет объектов для отображения в карточках.",
    }


def _format_price_short(price):
    if price >= 1_000_000:
        return f"{price / 1_000_000:.1f} млн ₽".replace(".0 ", " ")
    return f"{int(price):,} ₽".replace(",", " ")


def _format_price_compact(price):
    if not price:
        return "—"
    if price >= 1_000_000:
        return f"{price / 1_000_000:.1f} млн".replace(".0 ", " ")
    if price >= 1000:
        return f"{price / 1000:.0f} тыс."
    return str(int(price))


def _district_story(district, mode_label):
    highlights = district.get("highlights") or []
    if highlights:
        return highlights[0]
    return f"Сильный сценарий «{mode_label.lower()}» по текущему набору данных."


def _district_analytics_label(district):
    profile = district.get("profile_label") or "balanced"
    mapping = {
        "family-friendly": "Семейный кластер",
        "investment-friendly": "Инвест-кластер",
        "commute-friendly": "Транспортный кластер",
    }
    return mapping.get(profile, "Сбалансированный район")


def _district_zone_tone(rank, scenario_score):
    if rank == 1:
        return "prime"
    if scenario_score >= 74:
        return "strong"
    if scenario_score >= 62:
        return "stable"
    return "watch"


def _build_viewport_bounds(map_listings):
    if not map_listings:
        return None

    latitudes = sorted(item["lat"] for item in map_listings)
    longitudes = sorted(item["lon"] for item in map_listings)
    count = len(map_listings)

    lower_index = max(0, int(count * 0.12) - 1)
    upper_index = min(count - 1, int(count * 0.88))

    south = latitudes[lower_index]
    north = latitudes[upper_index]
    west = longitudes[lower_index]
    east = longitudes[upper_index]

    lat_padding = max((north - south) * 0.16, 0.012)
    lon_padding = max((east - west) * 0.16, 0.018)

    return [
        [round(west - lon_padding, 6), round(south - lat_padding, 6)],
        [round(east + lon_padding, 6), round(north + lat_padding, 6)],
    ]


def _build_map_center(map_listings, district_centroids):
    if not map_listings:
        return {"lat": 55.751244, "lon": 37.618423, "zoom": 10.8}

    weighted_points = []
    for district in district_centroids[:3]:
        weight = max(district.get("listing_count", 1), 1) * (1.4 if district.get("rank", 10) == 1 else 1.0)
        weighted_points.extend([(district["lat"], district["lon"])] * int(max(round(weight / 2), 1)))

    if not weighted_points:
        weighted_points = [(item["lat"], item["lon"]) for item in map_listings]

    avg_lat = sum(point[0] for point in weighted_points) / len(weighted_points)
    avg_lon = sum(point[1] for point in weighted_points) / len(weighted_points)

    return {"lat": round(avg_lat, 6), "lon": round(avg_lon, 6), "zoom": 11.2}


def _district_heat_level(rank, scenario_score):
    if rank == 1 or scenario_score >= 82:
        return "hot"
    if scenario_score >= 72:
        return "warm"
    if scenario_score >= 60:
        return "steady"
    return "cool"


def _offset_coordinates(lat, lon, radius_km, angle_rad):
    lat_offset = (radius_km / 111.0) * math.sin(angle_rad)
    lon_scale = max(math.cos(math.radians(lat)), 0.35)
    lon_offset = (radius_km / (111.0 * lon_scale)) * math.cos(angle_rad)
    return round(lon + lon_offset, 6), round(lat + lat_offset, 6)


def _district_polygon(points, fallback_lat, fallback_lon):
    if not points:
        radii = [1.05, 0.82, 0.98, 0.88, 1.04, 0.8, 0.94, 0.86]
        coordinates = []
        for index, radius in enumerate(radii):
            angle = (2 * math.pi * index) / len(radii)
            coordinates.append(_offset_coordinates(fallback_lat, fallback_lon, radius, angle))
        coordinates.append(coordinates[0])
        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coordinates],
            },
        }

    center_lat = sum(item["lat"] for item in points) / len(points)
    center_lon = sum(item["lon"] for item in points) / len(points)
    sectors = 12
    sector_radii = [0.55] * sectors

    for item in points:
        lat_delta = item["lat"] - center_lat
        lon_delta = (item["lon"] - center_lon) * max(math.cos(math.radians(center_lat)), 0.35)
        radius = max(math.sqrt(lat_delta**2 + lon_delta**2) * 111.0 + 0.45, 0.6)
        angle = math.atan2(lat_delta, lon_delta)
        if angle < 0:
            angle += 2 * math.pi
        bucket = min(sectors - 1, int((angle / (2 * math.pi)) * sectors))
        sector_radii[bucket] = max(sector_radii[bucket], radius)

    smoothed_radii = []
    for index, radius in enumerate(sector_radii):
        left = sector_radii[index - 1]
        right = sector_radii[(index + 1) % sectors]
        smoothed_radii.append(round((left + radius * 1.8 + right) / 3.8, 3))

    coordinates = []
    for index, radius in enumerate(smoothed_radii):
        angle = (2 * math.pi * index) / sectors
        coordinates.append(_offset_coordinates(center_lat, center_lon, radius, angle))
    coordinates.append(coordinates[0])

    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [coordinates],
        },
    }


def build_map_context(listings, districts, map_mode="overall", recommendations=None, selected_listing=None):
    scenario = MAP_MODE_CONFIG.get(map_mode, MAP_MODE_CONFIG["overall"])
    listing_score_key = scenario["listing_score_key"]
    district_score_key = scenario["district_score_key"]
    recommendations = recommendations or []

    district_price_per_m2 = {}
    for item in listings:
        district = item.get("district")
        if not district:
            continue
        district_price_per_m2.setdefault(district, []).append(item.get("price_per_m2") or 0)

    district_baselines = {
        district: (sum([value for value in values if value > 0]) / len([value for value in values if value > 0]))
        if [value for value in values if value > 0]
        else 0
        for district, values in district_price_per_m2.items()
    }

    map_listings = [
        {
            "id": item.get("id"),
            "title": item.get("title") or item.get("address"),
            "address": item.get("address"),
            "district": item.get("district"),
            "price": item.get("price", 0),
            "rooms": item.get("rooms", 0),
            "area": item.get("area", 0),
            "lat": item.get("lat"),
            "lon": item.get("lon"),
            "object_score": item.get("scores", {}).get("object_score", 0),
            "district_score": item.get("district_score", 0),
            "metro_station": item.get("metro_station", ""),
            "metro_time_min": item.get("metro_time_min"),
            "image_url": item.get("image_url", ""),
            "url": item.get("url", ""),
            "recommendation_reasons": item.get("recommendation_reasons", []),
            "price_per_m2": item.get("price_per_m2", 0),
            "scores": item.get("scores", {}),
            "geocode_status": item.get("geocode_status", ""),
            "geocode_source": item.get("geocode_source", ""),
            "source_label": item.get("source_label", "sample_data"),
            "source_trust_score": item.get("source_trust_score", 60),
            "source_trust_note": item.get("source_trust_note", "Источник требует ручной проверки"),
            "duplicate_count": item.get("duplicate_count", 1),
            "created_at": item.get("created_at"),
            "score_explainer": item.get("score_explainer", []),
            "trust_band": item.get("trust_band", "mid"),
        }
        for item in listings
        if item.get("lat") not in (None, 0, 0.0) and item.get("lon") not in (None, 0, 0.0)
    ]

    map_listings_sorted = sorted(
        map_listings,
        key=lambda item: (
            -(item.get("scores", {}).get(listing_score_key, 0)),
            -(item.get("scores", {}).get("object_score", 0)),
            item.get("price", 0),
        ),
    )
    top_pick_ids = {item["id"] for item in map_listings_sorted[:3]}
    best_value_listing = max(map_listings, key=lambda item: item.get("scores", {}).get("value_score", 0), default=None)

    for item in map_listings:
        display_lat, display_lon = _display_coordinates(item)
        baseline = district_baselines.get(item["district"], 0)
        fair_price_gap = round(((baseline - (item.get("price_per_m2") or baseline)) / baseline) * 100, 1) if baseline else 0
        confidence_score = 52
        if (item.get("geocode_source") or "").lower() in {"nominatim", "yandex-http", "cian-page"}:
            confidence_score += 14
        elif item.get("lat") and item.get("lon"):
            confidence_score += 7
        confidence_score += min(4, len([reason for reason in item.get("recommendation_reasons", []) if str(reason).strip()])) * 6
        confidence_score += 4 if item.get("metro_station") else 0
        item["lat"] = display_lat
        item["lon"] = display_lon
        item["price_label"] = _format_price_short(item.get("price", 0))
        item["price_compact"] = _format_price_compact(item.get("price", 0))
        item["scenario_score"] = round(item.get("scores", {}).get(listing_score_key, 0), 1)
        item["fair_price_gap"] = fair_price_gap
        item["confidence_score"] = min(96, confidence_score)
        item.update(_freshness_payload(item.get("created_at")))
        item.update(_geocode_quality_payload(item))
        item["trust_band"] = _trust_band(item.get("source_trust_score", 60))
        item["is_top_pick"] = item["id"] in top_pick_ids
        item["is_best_value"] = bool(best_value_listing and item["id"] == best_value_listing.get("id"))
        item["marker_tone"] = "high" if item["scenario_score"] >= 75 else "mid" if item["scenario_score"] >= 60 else "low"
        item["marker_badge"] = "Выгодно" if item["is_best_value"] else "Топ" if item["is_top_pick"] else "Выбор"
        if item["is_best_value"] and fair_price_gap > 0:
            item["marker_note"] = f"Справедливая цена: лучше медианы района на {abs(fair_price_gap)}%"
        elif item["is_top_pick"]:
            item["marker_note"] = f"Топ-подборка по сценарию «{scenario['label'].lower()}»"
        else:
            item["marker_note"] = f"{scenario['label']}: {item['scenario_score']}/100"

    selected_map_listing = None
    if selected_listing:
        selected_map_listing = next((item for item in map_listings if item.get("id") == selected_listing.get("id")), None)

    district_centroids = []
    ranked_districts = sorted(
        districts,
        key=lambda item: (-(item.get(district_score_key, item.get("district_score", 0))), item.get("avg_price", 0)),
    )
    district_ranks = {item["district"]: index + 1 for index, item in enumerate(ranked_districts)}

    for district in districts:
        district_points = [item for item in map_listings if item["district"] == district["district"]]
        if not district_points:
            continue
        lat = sum(item["lat"] for item in district_points) / len(district_points)
        lon = sum(item["lon"] for item in district_points) / len(district_points)
        district_centroids.append(
            {
                "district": district["district"],
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "district_score": district.get("district_score", 0),
                "listing_count": district.get("listing_count", len(district_points)),
                "quality_band": district.get("quality_band", ""),
                "transport_score": district.get("transport_score", 0),
                "infra_score": district.get("infra_score", 0),
                "family_score": district.get("family_score", 0),
                "investment_score": district.get("investment_score", 0),
                "budget_fit_score": district.get("budget_fit_score", 0),
                "avg_price": district.get("avg_price", 0),
                "avg_price_per_m2": district.get("avg_price_per_m2", 0),
                "profile_label": district.get("profile_label", ""),
                "profile_label_ru": _district_analytics_label(district),
                "highlights": district.get("highlights", []),
                "scenario_score": round(district.get(district_score_key, district.get("district_score", 0)), 1),
                "rank": district_ranks.get(district["district"], 0),
                "story": _district_story(district, scenario["label"]),
                "avg_price_label": _format_price_short(district.get("avg_price", 0)),
            }
        )

    district_centroids = sorted(district_centroids, key=lambda item: item["rank"])
    top_districts = district_centroids[:3]
    selected_district = district_centroids[0] if district_centroids else None
    top_pick_districts = [item["district"] for item in top_districts]
    best_value_district = min(
        district_centroids,
        key=lambda item: item.get("avg_price_per_m2") or float("inf"),
        default=None,
    )

    for district in district_centroids:
        district["zone_tone"] = _district_zone_tone(district["rank"], district["scenario_score"])
        district["heat_level"] = _district_heat_level(district["rank"], district["scenario_score"])
        district["is_top_district"] = bool(selected_district and district["district"] == selected_district["district"])
        district["is_best_value_area"] = bool(best_value_district and district["district"] == best_value_district["district"])
        district["market_share"] = round((district.get("listing_count", 0) / len(map_listings)) * 100, 1) if map_listings else 0

    priority_zones = [district for district in district_centroids if district["rank"] <= 3]
    strongest_scenario_areas = sorted(district_centroids, key=lambda item: (-item.get("scenario_score", 0), item.get("avg_price", 0)))[:4]

    market_balance = None
    if selected_district and best_value_district:
        if selected_district["district"] == best_value_district["district"]:
            market_balance = f"{selected_district['district']} одновременно лидирует по сценарию и цене/качеству."
        else:
            market_balance = f"Лидер сценария — {selected_district['district']}, зона value — {best_value_district['district']}."

    top_cluster_hint = None
    if map_listings_sorted:
        cluster_hint_items = map_listings_sorted[: min(6, len(map_listings_sorted))]
        cluster_avg = sum(item.get("price", 0) for item in cluster_hint_items) / len(cluster_hint_items)
        cluster_score = sum(item.get("scenario_score", 0) for item in cluster_hint_items) / len(cluster_hint_items)
        cluster_district = cluster_hint_items[0].get("district")
        top_cluster_hint = {
            "district": cluster_district,
            "count": len(cluster_hint_items),
            "avg_price": round(cluster_avg, 0),
            "score": round(cluster_score, 1),
            "label": f"{cluster_district}: концентрат сильных сигналов",
        }

    market_summary = {
        "listing_count": len(map_listings),
        "district_count": len(district_centroids),
        "avg_price": round(sum(item.get("price", 0) for item in map_listings) / len(map_listings), 0) if map_listings else 0,
        "best_district": selected_district["district"] if selected_district else "—",
        "best_value_cluster": top_cluster_hint["district"] if top_cluster_hint else (best_value_district["district"] if best_value_district else "—"),
        "market_balance": market_balance or "Сценарный лидер и value-зона разведены по карте.",
    }

    viewport_bounds = _build_viewport_bounds(map_listings)
    center = _build_map_center(map_listings, district_centroids)
    district_geojson_features = []
    real_geojson_map = _load_real_district_geojson()
    geojson_source = "file" if real_geojson_map else "generated"
    for district in district_centroids:
        district_points = [item for item in map_listings if item["district"] == district["district"]]
        feature = real_geojson_map.get(_normalize_district_name(district["district"]))
        if feature:
            feature = {
                "type": "Feature",
                "geometry": _simplify_geometry(feature.get("geometry")),
                "properties": dict(feature.get("properties") or {}),
            }
            geometry_source = "file"
        elif not real_geojson_map:
            feature = _district_polygon(district_points, district["lat"], district["lon"])
            geometry_source = "generated"
        else:
            continue
        feature["properties"] = {
            "district": district["district"],
            "rank": district["rank"],
            "scenario_score": district["scenario_score"],
            "listing_count": district["listing_count"],
            "zone_tone": district["zone_tone"],
            "heat_level": district["heat_level"],
            "is_top_district": district["is_top_district"],
            "is_best_value_area": district["is_best_value_area"],
            "geometry_source": geometry_source,
        }
        district_geojson_features.append(feature)

    return {
        "engine": "maplibre",
        "center": center,
        "viewport_bounds": viewport_bounds,
        "listings": map_listings,
        "districts": district_centroids,
        "district_geojson": {"type": "FeatureCollection", "features": district_geojson_features},
        "district_geojson_source": geojson_source,
        "stats": {
            "listing_count": len(map_listings),
            "district_count": len(district_centroids),
            "avg_price": round(sum(item.get("price", 0) for item in map_listings) / len(map_listings), 0) if map_listings else 0,
            "top_score": round(map_listings_sorted[0].get("scores", {}).get("object_score", 0), 1) if map_listings_sorted else 0,
        },
        "clustering": {
            "district_view_zoom": 10.6,
            "cluster_max_zoom": 13.6,
            "detail_zoom": 14.6,
            "price_marker_zoom": 14.2,
            "polygon_fade_zoom": 12.8,
            "base_cell": 0.018,
            "mid_cell": 0.0095,
            "detail_cell": 0.0042,
        },
        "scenario": {
            "key": map_mode,
            "label": scenario["label"],
            "description": scenario["description"],
            "accent": scenario["accent"],
            "workspace_title": scenario["workspace_title"],
            "workspace_subtitle": scenario["workspace_subtitle"],
            "listing_score_key": listing_score_key,
            "district_score_key": district_score_key,
        },
        "top_districts": top_districts,
        "selected_district": selected_district,
        "top_picks": map_listings_sorted[:3],
        "selected_listing": selected_map_listing,
        "best_value_listing": best_value_listing,
        "best_value_district": best_value_district,
        "priority_zones": priority_zones,
        "strongest_scenario_areas": strongest_scenario_areas,
        "top_cluster_hint": top_cluster_hint,
        "market_summary": market_summary,
        "top_pick_districts": top_pick_districts,
        "market_label": f"{len(map_listings)} объектов / {len(district_centroids)} районов",
        "story_points": [
            f"Активный режим: {scenario['label']}",
            f"Лучший район: {selected_district['district'] if selected_district else '—'}",
            f"Лучшая value-зона: {best_value_district['district'] if best_value_district else '—'}",
        ],
        "legend": [
            {"tone": "high", "label": "Сильный сигнал", "description": "Высокий приоритет по активному сценарию"},
            {"tone": "mid", "label": "Устойчивый вариант", "description": "Хороший баланс, но не лидер карты"},
            {"tone": "low", "label": "Низкий приоритет", "description": "Требует компромиссов по цене или качеству"},
        ],
        "has_map_data": bool(map_listings),
        "empty_message": "Нет координат для отображения на карте.",
        "district_analytics_label": _district_analytics_label(selected_district or {}),
    }


def build_compare_context(districts, compare_selection):
    selected = [district for district in districts if district["district"] in compare_selection][:2]
    comparison = None
    if len(selected) == 2:
        left, right = selected
        left_weights = left.get("score_weights") or {"object": 0.35, "transport": 0.20, "infra": 0.20, "family": 0.15, "investment": 0.10}
        right_weights = right.get("score_weights") or {"object": 0.35, "transport": 0.20, "infra": 0.20, "family": 0.15, "investment": 0.10}
        left_parts = {
            "Объекты": round(float(left.get("object_score", 0)) * float(left_weights.get("object", 0.35)), 1),
            "Транспорт": round(float(left.get("transport_score", 0)) * float(left_weights.get("transport", 0.20)), 1),
            "Инфраструктура": round(float(left.get("infra_score", 0)) * float(left_weights.get("infra", 0.20)), 1),
            "Семья": round(float(left.get("family_score", 0)) * float(left_weights.get("family", 0.15)), 1),
            "Инвестиции": round(float(left.get("investment_score", 0)) * float(left_weights.get("investment", 0.10)), 1),
        }
        right_parts = {
            "Объекты": round(float(right.get("object_score", 0)) * float(right_weights.get("object", 0.35)), 1),
            "Транспорт": round(float(right.get("transport_score", 0)) * float(right_weights.get("transport", 0.20)), 1),
            "Инфраструктура": round(float(right.get("infra_score", 0)) * float(right_weights.get("infra", 0.20)), 1),
            "Семья": round(float(right.get("family_score", 0)) * float(right_weights.get("family", 0.15)), 1),
            "Инвестиции": round(float(right.get("investment_score", 0)) * float(right_weights.get("investment", 0.10)), 1),
        }
        metrics = [
            ("Общий рейтинг", left["district_score"], right["district_score"]),
            ("Семья", left["family_score"], right["family_score"]),
            ("Инвестиции", left["investment_score"], right["investment_score"]),
            ("Транспорт", left["transport_score"], right["transport_score"]),
            ("Цена / качество", left["budget_fit_score"], right["budget_fit_score"]),
        ]

        def _winner_text(title, left_value, right_value):
            if left_value == right_value:
                return f"По метрике «{title.lower()}» районы выглядят на одном уровне."
            winner = left["district"] if left_value > right_value else right["district"]
            return f"По метрике «{title.lower()}» лидирует {winner}."

        comparison = {
            "left": left,
            "right": right,
            "winner": left["district"] if left["district_score"] >= right["district_score"] else right["district"],
            "price_gap": round(abs(left["avg_price"] - right["avg_price"]), 2),
            "score_gap": round(abs(left["district_score"] - right["district_score"]), 2),
            "scenario_cards": [
                {
                    "label": "Для семьи",
                    "left": round(left["family_score"], 1),
                    "right": round(right["family_score"], 1),
                    "winner": left["district"] if left["family_score"] >= right["family_score"] else right["district"],
                    "verdict": f"{left['district']}" if left["family_score"] >= right["family_score"] else f"{right['district']}"
                },
                {
                    "label": "Для инвестиций",
                    "left": round(left["investment_score"], 1),
                    "right": round(right["investment_score"], 1),
                    "winner": left["district"] if left["investment_score"] >= right["investment_score"] else right["district"],
                    "verdict": f"{left['district']}" if left["investment_score"] >= right["investment_score"] else f"{right['district']}"
                },
                {
                    "label": "Транспорт",
                    "left": round(left["transport_score"], 1),
                    "right": round(right["transport_score"], 1),
                    "winner": left["district"] if left["transport_score"] >= right["transport_score"] else right["district"],
                    "verdict": f"{left['district']}" if left["transport_score"] >= right["transport_score"] else f"{right['district']}"
                },
                {
                    "label": "Цена / качество",
                    "left": round(left["budget_fit_score"], 1),
                    "right": round(right["budget_fit_score"], 1),
                    "winner": left["district"] if left["budget_fit_score"] >= right["budget_fit_score"] else right["district"],
                    "verdict": f"{left['district']}" if left["budget_fit_score"] >= right["budget_fit_score"] else f"{right['district']}"
                },
            ],
            "metric_bars": [
                {
                    "label": label,
                    "left_value": round(left_value, 1),
                    "right_value": round(right_value, 1),
                    "left_width": round((left_value / 100) * 100, 1),
                    "right_width": round((right_value / 100) * 100, 1),
                    "verdict": _winner_text(label, left_value, right_value),
                }
                for label, left_value, right_value in metrics
            ],
            "verdict": f"{left['district']} лучше подойдёт тем, кто ценит баланс, если важнее общий quality score." if left["district_score"] >= right["district_score"] else f"{right['district']} выглядит сильнее как сценарий без явных компромиссов по текущим данным.",
            "tradeoffs": [
                f"{left['district']} сильнее по транспорту" if left["transport_score"] > right["transport_score"] else f"{right['district']} сильнее по транспорту",
                f"{left['district']} лучше для семьи" if left["family_score"] > right["family_score"] else f"{right['district']} лучше для семьи",
                f"{left['district']} выглядит доступнее по бюджету" if left["budget_fit_score"] > right["budget_fit_score"] else f"{right['district']} выглядит доступнее по бюджету",
            ],
            "confidence_note": "Сравнение учитывает score района, цену, транспорт и сценарные подоценки по текущей выборке.",
            "ranking_explainer": [
                {
                    "label": label,
                    "left_share": round((left_parts[label] / (sum(left_parts.values()) or 1)) * 100),
                    "right_share": round((right_parts[label] / (sum(right_parts.values()) or 1)) * 100),
                    "winner": left["district"] if left_parts[label] >= right_parts[label] else right["district"],
                }
                for label in left_parts
            ],
            "district_explanations": [
                (
                    f"{left['district']} выше по метрике «{label.lower()}», потому что дает {left_parts[label]:.1f} score-пункта против {right_parts[label]:.1f} у {right['district']}."
                    if left_parts[label] > right_parts[label]
                    else f"{right['district']} выше по метрике «{label.lower()}», потому что дает {right_parts[label]:.1f} score-пункта против {left_parts[label]:.1f} у {left['district']}."
                    if right_parts[label] > left_parts[label]
                    else f"По метрике «{label.lower()}» районы идут почти вровень: {left_parts[label]:.1f} против {right_parts[label]:.1f}."
                )
                for label in left_parts
            ],
        }
    return {
        "selection": compare_selection,
        "districts": districts,
        "comparison": comparison,
    }
