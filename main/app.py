# main/app.py
import os

from flask import Flask, render_template, request

from backend.config import DEFAULT_DB_PATH
from frontend.filters import build_page_context


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "frontend", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "frontend", "static")


def create_app(test_config=None):
    app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
    app.config.from_mapping(
        DB_PATH=str(DEFAULT_DB_PATH),
        TESTING=False,
    )

    if test_config:
        app.config.update(test_config)

    @app.route("/", methods=["GET", "POST"])
    def index():
        form = request.form if request.method == "POST" else None
        context = build_page_context(form=form, db_path=app.config.get("DB_PATH"))
        return render_template("index.html", **context)

    return app


app = create_app()
