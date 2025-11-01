# filters.py
import math


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

        filtered_data = self.get_filtered_data()
        return filtered_data

    def reset_filter(self):
        self.price_range = [0, 1000000]
        self.rooms = None
        self.district = None
        self.chart_type = "bar"
        return self.get_filtered_data()

    def get_filtered_data(self):
        sample_data = [
            {"id": 1, "price": 500000, "rooms": 2, "district": "Центральный",
             "lat": 55.7558, "lon": 37.6173, "address": "ул. Тверская, д. 15"},
            {"id": 2, "price": 750000, "rooms": 3, "district": "Северный",
             "lat": 55.835, "lon": 37.625,
             "address": "пр. Ленинградский, д. 42"},
            {"id": 3, "price": 300000, "rooms": 1, "district": "Южный",
             "lat": 55.645, "lon": 37.625,
             "address": "ул. Чертановская, д. 28"},
            {"id": 4, "price": 900000, "rooms": 4, "district": "Западный",
             "lat": 55.734, "lon": 37.585,
             "address": "ул. Можайский Вал, д. 12"},
            {"id": 5, "price": 450000, "rooms": 2, "district": "Восточный",
             "lat": 55.787, "lon": 37.725,
             "address": "ул. Щербаковская, д. 35"},
            {"id": 6, "price": 600000, "rooms": 3, "district": "Центральный",
             "lat": 55.752, "lon": 37.605, "address": "ул. Арбат, д. 23"},
            {"id": 7, "price": 550000, "rooms": 2, "district": "Северный",
             "lat": 55.845, "lon": 37.635,
             "address": "ул. Фестивальная, д. 18"},
            {"id": 8, "price": 400000, "rooms": 1, "district": "Южный",
             "lat": 55.625, "lon": 37.615,
             "address": "ул. Кировоградская, д. 7"},
            {"id": 9, "price": 800000, "rooms": 3, "district": "Западный",
             "lat": 55.724, "lon": 37.495,
             "address": "ул. Кутузовский проспект, д. 31"},
            {"id": 10, "price": 350000, "rooms": 1, "district": "Восточный",
             "lat": 55.807, "lon": 37.785,
             "address": "ул. Первомайская, д. 44"},
            {"id": 11, "price": 650000, "rooms": 2, "district": "Центральный",
             "lat": 55.745, "lon": 37.635, "address": "ул. Пятницкая, д. 19"},
            {"id": 12, "price": 950000, "rooms": 4, "district": "Северный",
             "lat": 55.875, "lon": 37.545, "address": "ул. Дубнинская, д. 5"},
        ]

        sample_data = sorted(sample_data, key=lambda x: x['price'], reverse=True)

        filtered = []
        for item in sample_data:
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
            return self._create_bar_chart()
        elif chart_type == "pie":
            return self._create_pie_chart()
        elif chart_type == "line":
            return self._create_line_chart()
        elif chart_type == "table":
            return self._create_table()

    def update_chart(self, data):
        self.data = data
        return self.draw_chart(data, self.chart_type)

    def _create_bar_chart(self):
        districts = {}
        for item in self.data:
            district = item["district"]
            if district not in districts:
                districts[district] = 0
            districts[district] += 1

        chart_html = f"""
        <div class="chart-container">
            <h3>Распределение объявлений по районам</h3>
            <div class="bar-chart">
        """

        for district, count in districts.items():
            width = count * 50
            chart_html += f"""
                <div class="bar-item">
                    <div class="bar-label">{district}</div>
                    <div class="bar" style="width: {width}px;">
                        <span class="bar-value">{count}</span>
                    </div>
                </div>
            """

        chart_html += "</div></div>"
        return chart_html

    def _create_pie_chart(self):
        rooms_count = {}
        for item in self.data:
            rooms = item["rooms"]
            if rooms not in rooms_count:
                rooms_count[rooms] = 0
            rooms_count[rooms] += 1

        if not rooms_count:
            return "<div class='chart-container'><h3>Распределение по количеству комнат</h3><p>Нет данных для отображения</p></div>"

        total = sum(rooms_count.values())
        colors = ["#ff6384", "#36a2eb", "#ffce56", "#4bc0c0", "#9966ff",
                  "#ff9f40", "#8ac6d1", "#ff6b6b"]

        chart_html = """
        <div class="chart-container">
            <h3>Распределение по количеству комнат</h3>
            <div class="pie-chart-container">
                <div class="pie-svg-container">
                    <svg width="200" height="200" viewBox="0 0 200 200" class="pie-svg">
        """

        current_angle = 0
        center_x, center_y = 100, 100
        radius = 80

        for i, (rooms, count) in enumerate(rooms_count.items()):
            percentage = count / total
            angle = percentage * 360
            color = colors[i % len(colors)]

            if angle == 360:
                chart_html += f'<circle cx="{center_x}" cy="{center_y}" r="{radius}" fill="{color}" />'
            else:
                start_angle = current_angle
                end_angle = current_angle + angle

                start_rad = (start_angle - 90) * 3.14159 / 180
                end_rad = (end_angle - 90) * 3.14159 / 180

                start_x = center_x + radius * math.cos(start_rad)
                start_y = center_y + radius * math.sin(start_rad)
                end_x = center_x + radius * math.cos(end_rad)
                end_y = center_y + radius * math.sin(end_rad)

                large_arc_flag = 1 if angle > 180 else 0

                chart_html += f'''
                <path d="M {center_x} {center_y} L {start_x} {start_y} A {radius} {radius} 0 {large_arc_flag} 1 {end_x} {end_y} Z" 
                      fill="{color}" stroke="white" stroke-width="2" />
                '''

            current_angle += angle

        chart_html += """
                    </svg>
                </div>
                <div class="pie-legend">
        """

        for i, (rooms, count) in enumerate(rooms_count.items()):
            percentage = (count / total) * 100
            color = colors[i % len(colors)]
            chart_html += f"""
                    <div class="pie-legend-item">
                        <div class="pie-color" style="background-color: {color};"></div>
                        <span>{rooms} комн.: {count} ({percentage:.1f}%)</span>
                    </div>
            """

        chart_html += """
                </div>
            </div>
        </div>
        """
        return chart_html

    def _create_line_chart(self):
        prices = [item["price"] for item in self.data]
        prices.sort()

        chart_html = """
        <div class="chart-container">
            <h3>Динамика цен</h3>
            <div class="line-chart">
        """

        if prices:
            max_price = max(prices)
            for i, price in enumerate(prices):
                height = (price / max_price) * 100
                chart_html += f"""
                    <div class="line-point" style="height: {height}px;" title="{price:,} руб.">
                        <span class="point-value">{i + 1}</span>
                    </div>
                """

        chart_html += "</div></div>"
        return chart_html

    def _create_table(self):
        chart_html = """
        <div class="chart-container">
            <h3>Таблица данных</h3>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Цена</th>
                        <th>Комнат</th>
                        <th>Район</th>
                        <th>Адрес</th>
                    </tr>
                </thead>
                <tbody>
        """

        for item in self.data:
            chart_html += f"""
                <tr>
                    <td>{item['id']}</td>
                    <td>{item['price']:,} руб.</td>
                    <td>{item['rooms']}</td>
                    <td>{item['district']}</td>
                    <td>{item['address']}</td>
                </tr>
            """

        chart_html += """
                </tbody>
            </table>
        </div>
        """
        return chart_html


class MapView:
    def __init__(self):
        self.markers = []

    def render(self, data):
        self.markers = data
        return self._create_map_html()

    def update_markers(self, data):
        self.markers = data
        return self._create_map_html()

    def _create_map_html(self):
        map_html = """
        <div class="map-container">
            <h3>Карта объявлений</h3>
            <div class="simple-map">
        """

        for marker in self.markers:
            map_html += f"""
                <div class="map-marker">
                    <div class="marker-dot"></div>
                    <div class="marker-info">
                        <strong>{marker['price']:,} руб.</strong><br>
                        {marker['rooms']} комн.<br>
                        {marker['district']}<br>
                        <small>{marker['address']}</small>
                    </div>
                </div>
            """

        if not self.markers:
            map_html += "<p>Нет данных для отображения</p>"

        map_html += "</div></div>"
        return map_html
