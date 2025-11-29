# frontend/filters.py
import sqlite3
import os
from html_renderer import (
    render_bar_chart,
    render_pie_chart,
    render_line_chart,
    render_table,
    render_map)


def load_data_from_db(db_path="data.db"):
    if not os.path.exists(db_path):
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM listings")
    rows = cur.fetchall()
    conn.close()

    data = []
    for row in rows:
        try:
            price = float(row["price"]) if row["price"] else 0
        except (ValueError, TypeError):
            price = 0

        item = {
            "id": row["id"],
            "price": price,
            "rooms": int(row.get("rooms", 0)) if row.get("rooms") else 0,
            "district": row.get("district", "Неизвестный"),
            "lat": float(row.get("lat", 0.0)) if row.get("lat") else 0.0,
            "lon": float(row.get("lon", 0.0)) if row.get("lon") else 0.0,
            "address": row.get("address", "Адрес не указан"),
        }
        data.append(item)
    return data


class FilterPanel:
    def __init__(self):
        self.price_range = [0, 1000000]
        self.rooms = None
        self.district = None
        self.chart_type = "bar"

    def apply_filter(self, price_range=None, rooms=None, district=None,
                     chart_type=None):
        if price_range:
            self.price_range = price_range
        if rooms:
            self.rooms = rooms
        if district:
            self.district = district
        if chart_type:
            self.chart_type = chart_type
        return self.get_filtered_data()

    def reset_filter(self):
        self.price_range = [0, 1000000]
        self.rooms = None
        self.district = None
        self.chart_type = "bar"
        return self.get_filtered_data()

    def get_filtered_data(self):
        all_data = load_data_from_db()
        all_data.sort(key=lambda x: x['price'], reverse=True)
        filtered = []
        for item in all_data:
            if (self.price_range[0] <= item["price"] <= self.price_range[1] and
                    (self.rooms is None or item["rooms"] == self.rooms) and
                    (self.district is None or item[
                        "district"] == self.district)):
                filtered.append(item)
        return filtered


class ChartView:
    def __init__(self):
        self.chart_type = "bar"
        self.data = []

    def draw_chart(self, data, chart_type="bar"):
        self.data = data
        self.chart_type = chart_type
        if chart_type == "bar":
            return render_bar_chart(data)
        elif chart_type == "pie":
            return render_pie_chart(data)
        elif chart_type == "line":
            return render_line_chart(data)
        elif chart_type == "table":
            return render_table(data)
        else:
            return "<p>Неизвестный тип диаграммы</p>"

    def update_chart(self, data):
        self.data = data
        return self.draw_chart(data, self.chart_type)


class MapView:
    def __init__(self):
        self.markers = []

    def render(self, data):
        self.markers = data
        return render_map(data)

    def update_markers(self, data):
        self.markers = data
        return render_map(data)
