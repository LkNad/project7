from __future__ import annotations

from flask import Blueprint, current_app, make_response, render_template, request

from frontend.filters import build_district_detail_context, build_listing_detail_context, build_page_context
from main.web import apply_saved_state, get_or_create_visitor_id, load_data_quality, load_saved_lists, load_user_weights, set_visitor_cookie


workspace_bp = Blueprint("workspace", __name__)


def _render_workspace(template_name, page_kind):
    form = request.form if request.method == "POST" else request.args
    db_path = current_app.config.get("DB_PATH")
    user_weights = load_user_weights(db_path)
    context = build_page_context(form=form, db_path=db_path, user_weights=user_weights)
    visitor_id = get_or_create_visitor_id()
    context = apply_saved_state(context, load_saved_lists(db_path, visitor_id))
    context["data_quality_report"] = load_data_quality(db_path)
    context["page_kind"] = page_kind
    response = make_response(render_template(template_name, **context))
    return set_visitor_cookie(response, visitor_id)


@workspace_bp.route("/", methods=["GET", "POST"], endpoint="index")
@workspace_bp.route("/analytics", methods=["GET", "POST"])
def index():
    return _render_workspace("index.html", "analytics")


@workspace_bp.route("/map", methods=["GET", "POST"], endpoint="map_page")
def map_page():
    return _render_workspace("index.html", "map")


@workspace_bp.route("/listing/<int:listing_id>", methods=["GET"], endpoint="listing_detail")
def listing_detail(listing_id):
    db_path = current_app.config.get("DB_PATH")
    context = build_listing_detail_context(
        listing_id=listing_id,
        db_path=db_path,
        form=request.args,
        user_weights=load_user_weights(db_path),
    )
    visitor_id = get_or_create_visitor_id()
    saved_lists = load_saved_lists(db_path, visitor_id)
    listing = context.get("listing")
    if listing:
        listing["is_favorite"] = listing.get("id") in saved_lists.get("favorite", set())
        listing["is_saved_shortlist"] = listing.get("id") in saved_lists.get("shortlist", set())
    response = make_response(render_template("object_detail.html", **context))
    return set_visitor_cookie(response, visitor_id)


@workspace_bp.route("/district/<path:district_name>", methods=["GET"], endpoint="district_detail")
def district_detail(district_name):
    db_path = current_app.config.get("DB_PATH")
    context = build_district_detail_context(
        district_name=district_name,
        db_path=db_path,
        form=request.args,
        user_weights=load_user_weights(db_path),
    )
    visitor_id = get_or_create_visitor_id()
    response = make_response(render_template("district_detail.html", **context))
    return set_visitor_cookie(response, visitor_id)


@workspace_bp.route("/methodology", methods=["GET"], endpoint="methodology_page")
def methodology_page():
    response = make_response(render_template("methodology.html"))
    return set_visitor_cookie(response, get_or_create_visitor_id())


@workspace_bp.route("/data-quality", methods=["GET"], endpoint="data_quality_page")
def data_quality_page():
    context = {"quality": load_data_quality(current_app.config.get("DB_PATH"))}
    response = make_response(render_template("data_quality.html", **context))
    return set_visitor_cookie(response, get_or_create_visitor_id())
