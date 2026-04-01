import os

from flask import Flask, jsonify, render_template, request

from backend.DataFetcher import DataFetcher
from backend.config import DEFAULT_DB_PATH
from frontend.filters import build_page_context


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "frontend", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "frontend", "static")


def _json_response(context):
    return {
        "summary": context["summary"],
        "listings": context["listings"],
        "districts": context["districts"],
        "shortlist": context["shortlist"],
        "recommendations": context["recommendations"],
        "compare": context["compare"],
        "status": context["status"],
        "results_count": context["results_count"],
        "total_count": context["total_count"],
    }


def create_app(test_config=None):
    app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
    app.config.from_mapping(
        DB_PATH=str(DEFAULT_DB_PATH),
        TESTING=False,
        AUTO_BOOTSTRAP_RUNTIME_DATASET=True,
        DEFAULT_RUNTIME_SOURCE="test://default",
    )
    if test_config:
        app.config.update(test_config)

    if app.config.get("AUTO_BOOTSTRAP_RUNTIME_DATASET") and not app.config.get("TESTING"):
        DataFetcher(
            source=app.config.get("DEFAULT_RUNTIME_SOURCE", "test://default"),
            db_path=app.config.get("DB_PATH"),
        ).ensure_runtime_database(
            source=app.config.get("DEFAULT_RUNTIME_SOURCE", "test://default"),
            bootstrap_if_empty=True,
        )

    def _render_workspace(template_name, page_kind):
        form = request.form if request.method == "POST" else request.args
        context = build_page_context(form=form, db_path=app.config.get("DB_PATH"))
        context["page_kind"] = page_kind
        return render_template(template_name, **context)

    @app.route("/", methods=["GET", "POST"])
    @app.route("/analytics", methods=["GET", "POST"])
    def index():
        return _render_workspace("index.html", "analytics")

    @app.route("/map", methods=["GET", "POST"])
    def map_page():
        return _render_workspace("index.html", "map")

    @app.route("/api/listings", methods=["GET"])
    def api_listings():
        context = build_page_context(form=request.args, db_path=app.config.get("DB_PATH"))
        return jsonify(_json_response(context))

    @app.route("/api/districts", methods=["GET"])
    def api_districts():
        context = build_page_context(form=request.args, db_path=app.config.get("DB_PATH"))
        return jsonify({"districts": context["districts"], "status": context["status"]})

    @app.route("/api/recommendations", methods=["GET"])
    def api_recommendations():
        context = build_page_context(form=request.args, db_path=app.config.get("DB_PATH"))
        return jsonify({"shortlist": context["shortlist"], "recommendations": context["recommendations"]})

    @app.route("/api/compare", methods=["GET"])
    def api_compare():
        context = build_page_context(form=request.args, db_path=app.config.get("DB_PATH"))
        return jsonify(context["compare"])

    return app


app = create_app()
