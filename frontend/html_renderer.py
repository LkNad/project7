# frontend/html_renderer.py
import math


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
    "#ff6384",
    "#36a2eb",
    "#ffce56",
    "#4bc0c0",
    "#9966ff",
    "#ff9f40",
    "#8ac6d1",
    "#ff6b6b",
]


def _group_counts(data, key):
    grouped = {}
    for item in data:
        grouped[item[key]] = grouped.get(item[key], 0) + 1
    return grouped


def build_chart_context(data, chart_type="bar"):
    chart_type = chart_type or "bar"
    if chart_type == "pie":
        return build_pie_chart_context(data)
    if chart_type == "line":
        return build_line_chart_context(data)
    if chart_type == "table":
        return {"type": "table", "title": "Таблица данных", "rows": data, "empty_message": "Нет данных для отображения"}
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
        for district, count in districts.items()
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


def build_line_chart_context(data):
    prices = sorted(item["price"] for item in data)
    if not prices:
        return {
            "type": "line",
            "title": "Распределение цен по выборке",
            "points": [],
            "empty_message": "Нет данных для отображения",
        }

    max_price = max(prices)
    if max_price <= 0:
        return {
            "type": "line",
            "title": "Распределение цен по выборке",
            "points": [],
            "empty_message": "Нет корректных данных о ценах",
        }

    points = [
        {
            "price": price,
            "height_percent": round((price / max_price) * 100, 2),
            "index": index + 1,
        }
        for index, price in enumerate(prices)
    ]
    return {
        "type": "line",
        "title": "Распределение цен по выборке",
        "points": points,
        "empty_message": "Нет данных для отображения",
    }


def build_listing_cards_context(data):
    return {
        "title": "Карта и карточки объектов",
        "items": data,
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


def build_map_context(listings, districts, map_mode="overall", recommendations=None):
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
        baseline = district_baselines.get(item["district"], 0)
        fair_price_gap = round(((baseline - (item.get("price_per_m2") or baseline)) / baseline) * 100, 1) if baseline else 0
        item["price_label"] = _format_price_short(item.get("price", 0))
        item["price_compact"] = _format_price_compact(item.get("price", 0))
        item["scenario_score"] = round(item.get("scores", {}).get(listing_score_key, 0), 1)
        item["fair_price_gap"] = fair_price_gap
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
    for district in district_centroids:
        district_points = [item for item in map_listings if item["district"] == district["district"]]
        feature = _district_polygon(district_points, district["lat"], district["lon"])
        feature["properties"] = {
            "district": district["district"],
            "rank": district["rank"],
            "scenario_score": district["scenario_score"],
            "listing_count": district["listing_count"],
            "zone_tone": district["zone_tone"],
            "heat_level": district["heat_level"],
            "is_top_district": district["is_top_district"],
            "is_best_value_area": district["is_best_value_area"],
        }
        district_geojson_features.append(feature)

    return {
        "engine": "maplibre",
        "center": center,
        "viewport_bounds": viewport_bounds,
        "listings": map_listings,
        "districts": district_centroids,
        "district_geojson": {"type": "FeatureCollection", "features": district_geojson_features},
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
        metrics = [
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
        }
    return {
        "selection": compare_selection,
        "districts": districts,
        "comparison": comparison,
    }
