# frontend/html_renderer.py
import math


def render_bar_chart(data):
    districts = {}
    for item in data:
        district = item["district"]
        districts[district] = districts.get(district, 0) + 1

    chart_html = """
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


def render_pie_chart(data):
    rooms_count = {}
    for item in data:
        rooms = item["rooms"]
        rooms_count[rooms] = rooms_count.get(rooms, 0) + 1

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
            start_rad = (start_angle - 90) * math.pi / 180
            end_rad = (end_angle - 90) * math.pi / 180
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


def render_line_chart(data):
    prices = sorted([item["price"] for item in data])
    chart_html = """
    <div class="chart-container">
        <h3>Динамика цен</h3>
        <div class="line-chart">
    """
    if prices:
        max_price = max(prices)
        if max_price > 0:
            for i, price in enumerate(prices):
                height = (price / max_price) * 100
                chart_html += f"""
                    <div class="line-point" style="height: {height}px; border" title="{price:,} руб.">
                        <span class="point-value">{price}</span>
                    </div>
                """
        else:
            # Все цены — ноль или отрицательные
            chart_html += "<p>Нет корректных данных о ценах</p>"
    else:
        chart_html += "<p>Нет данных для отображения</p>"
    chart_html += "</div></div>"
    return chart_html


def render_table(data):
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
    for item in data:
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


def render_map(data):
    map_html = """
    <div class="map-container">
        <h3>Карта объявлений</h3>
        <div class="simple-map">
    """
    for marker in data:
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
    if not data:
        map_html += "<p>Нет данных для отображения</p>"
    map_html += "</div></div>"
    return map_html
