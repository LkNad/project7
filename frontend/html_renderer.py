# frontend/html_renderer.py
import math


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
        "title": "Карточки объектов",
        "items": data,
        "empty_message": "Нет объектов для отображения в карточках.",
    }
