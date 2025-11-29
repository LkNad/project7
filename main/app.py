# main/app.py
from flask import Flask, render_template, request
import os

from frontend.filters import FilterPanel, ChartView, MapView

app = Flask(__name__)

template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            '../frontend/templates')
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../frontend/static')

app = Flask(__name__,
            template_folder=template_dir,
            static_folder=static_dir)

filter_panel = FilterPanel()
chart_view = ChartView()
map_view = MapView()


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'apply_filters':
            price_min = request.form.get('price_min', type=int)
            price_max = request.form.get('price_max', type=int)
            rooms = request.form.get('rooms', type=int)
            district = request.form.get('district')
            chart_type = request.form.get('chart_type', 'bar')

            filtered_data = filter_panel.apply_filter(
                price_range=[price_min or 0, price_max or 1000000],
                rooms=rooms if rooms else None,
                district=district if district else None,
                chart_type=chart_type
            )
        elif action == 'reset_filters':
            filtered_data = filter_panel.reset_filter()
        else:
            filtered_data = filter_panel.get_filtered_data()
    else:
        filtered_data = filter_panel.get_filtered_data()

    chart_html = chart_view.draw_chart(filtered_data, filter_panel.chart_type)
    map_html = map_view.render(filtered_data)

    return render_template('index.html',
                           chart_html=chart_html,
                           map_html=map_html,
                           current_filters=filter_panel,
                           results_count=len(filtered_data))
