from __future__ import annotations

import json
import secrets
import sqlite3

from flask import Blueprint, current_app, jsonify, make_response, request, url_for

from frontend.filters import build_page_context
from main.web import (
    ensure_saved_lists_table,
    ensure_user_tables,
    fetch_listing_record,
    get_or_create_visitor_id,
    json_response,
    load_saved_lists,
    load_user_weights,
    owner_key,
    record_event,
    set_visitor_cookie,
)


api_bp = Blueprint("api", __name__)


@api_bp.route("/api/listings", methods=["GET"], endpoint="api_listings")
def api_listings():
    db_path = current_app.config.get("DB_PATH")
    context = build_page_context(form=request.args, db_path=db_path, user_weights=load_user_weights(db_path))
    return jsonify(json_response(context))


@api_bp.route("/api/districts", methods=["GET"], endpoint="api_districts")
def api_districts():
    db_path = current_app.config.get("DB_PATH")
    context = build_page_context(form=request.args, db_path=db_path, user_weights=load_user_weights(db_path))
    return jsonify({"districts": context["districts"], "status": context["status"]})


@api_bp.route("/api/recommendations", methods=["GET"], endpoint="api_recommendations")
def api_recommendations():
    db_path = current_app.config.get("DB_PATH")
    context = build_page_context(form=request.args, db_path=db_path, user_weights=load_user_weights(db_path))
    return jsonify({"shortlist": context["shortlist"], "recommendations": context["recommendations"]})


@api_bp.route("/api/compare", methods=["GET"], endpoint="api_compare")
def api_compare():
    db_path = current_app.config.get("DB_PATH")
    context = build_page_context(form=request.args, db_path=db_path, user_weights=load_user_weights(db_path))
    return jsonify(context["compare"])


@api_bp.route("/api/bootstrap-status", methods=["GET"], endpoint="api_bootstrap_status")
def api_bootstrap_status():
    return jsonify(current_app.config.get("BOOTSTRAP_STATUS", {"state": "idle", "error": ""}))


@api_bp.route("/api/saved-lists", methods=["GET", "POST"], endpoint="api_saved_lists")
def api_saved_lists():
    visitor_id = get_or_create_visitor_id()
    db_path = current_app.config.get("DB_PATH")
    ensure_saved_lists_table(db_path)
    owner_key_value = owner_key(visitor_id)
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        listing_id = int(payload.get("listing_id", 0))
        list_type = payload.get("list_type")
        if list_type not in {"favorite", "shortlist", "compare"} or listing_id <= 0:
            response = make_response(jsonify({"ok": False, "error": "invalid payload"}), 400)
            return set_visitor_cookie(response, visitor_id)
        with sqlite3.connect(str(db_path)) as conn:
            compare_count = 0
            if list_type == "compare":
                compare_count = conn.execute(
                    "SELECT COUNT(*) FROM saved_lists WHERE visitor_id = ? AND list_type = 'compare'",
                    (owner_key_value,),
                ).fetchone()[0]
            listing = fetch_listing_record(conn, listing_id)
            if not listing:
                response = make_response(jsonify({"ok": False, "error": "listing not found"}), 404)
                return set_visitor_cookie(response, visitor_id)
            exists = conn.execute(
                "SELECT 1 FROM saved_lists WHERE visitor_id = ? AND listing_key = ? AND list_type = ?",
                (owner_key_value, listing["listing_key"], list_type),
            ).fetchone()
            if exists:
                conn.execute(
                    "DELETE FROM saved_lists WHERE visitor_id = ? AND listing_key = ? AND list_type = ?",
                    (owner_key_value, listing["listing_key"], list_type),
                )
                active = False
            else:
                if list_type == "compare" and compare_count >= 2:
                    oldest = conn.execute(
                        "SELECT id FROM saved_lists WHERE visitor_id = ? AND list_type = 'compare' ORDER BY created_at ASC, id ASC LIMIT 1",
                        (owner_key_value,),
                    ).fetchone()
                    if oldest:
                        conn.execute("DELETE FROM saved_lists WHERE id = ?", (oldest[0],))
                conn.execute(
                    "INSERT OR IGNORE INTO saved_lists (visitor_id, listing_id, listing_key, list_type) VALUES (?, ?, ?, ?)",
                    (owner_key_value, listing["id"], listing["listing_key"], list_type),
                )
                active = True
            conn.commit()
        record_event(
            db_path,
            owner_key_value,
            f"saved_list_{list_type}",
            {"listing_id": listing_id, "listing_key": listing["listing_key"], "active": active},
        )
        response = make_response(jsonify({"ok": True, "active": active}))
        return set_visitor_cookie(response, visitor_id)

    payload = load_saved_lists(db_path, visitor_id)
    response = make_response(jsonify({key: sorted(list(value)) for key, value in payload.items()}))
    return set_visitor_cookie(response, visitor_id)


@api_bp.route("/api/share-report", methods=["POST"], endpoint="api_share_report")
def api_share_report():
    visitor_id = get_or_create_visitor_id()
    db_path = current_app.config.get("DB_PATH")
    ensure_user_tables(db_path)
    owner_key_value = owner_key(visitor_id)
    payload = request.get_json(silent=True) or {}
    report_type = payload.get("report_type")
    if report_type not in {"shortlist", "compare"}:
        return jsonify({"ok": False, "error": "invalid type"}), 400
    saved = load_saved_lists(db_path, visitor_id)
    ids = sorted(list(saved.get(report_type, set())))
    context = build_page_context(form=request.args, db_path=db_path, user_weights=load_user_weights(db_path))
    listing_map = {item.get("id"): item for item in context.get("listing_cards", {}).get("items", [])}
    items = [listing_map[item_id] for item_id in ids if item_id in listing_map]
    token = secrets.token_urlsafe(10)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO report_shares (token, owner_key, report_type, payload) VALUES (?, ?, ?, ?)",
            (token, owner_key_value, report_type, json.dumps(items, ensure_ascii=False)),
        )
        conn.commit()
    record_event(db_path, owner_key_value, f"share_{report_type}", {"token": token, "count": len(items)})
    response = make_response(
        jsonify(
            {
                "ok": True,
                "url": url_for("reports.shared_report", token=token, _external=True),
                "pdf_url": url_for("reports.shared_report_pdf", token=token, _external=True),
            }
        )
    )
    return set_visitor_cookie(response, visitor_id)
