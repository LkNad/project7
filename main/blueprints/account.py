from __future__ import annotations

import json
import sqlite3

from flask import Blueprint, current_app, make_response, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from frontend.filters import build_page_context
from main.web import build_before_after_ranking, build_compare_dashboard, ensure_user_tables, get_or_create_visitor_id, load_saved_lists, load_user_weights, migrate_saved_lists, owner_key, record_event, set_visitor_cookie


account_bp = Blueprint("account", __name__)


def _cards_by_ids(context, listing_ids):
    listing_map = {item.get("id"): item for item in context.get("listing_cards", {}).get("items", [])}
    return [listing_map[item_id] for item_id in listing_ids if item_id in listing_map]


@account_bp.route("/account", methods=["GET", "POST"], endpoint="account_page")
def account_page():
    visitor_id = get_or_create_visitor_id()
    db_path = current_app.config.get("DB_PATH")
    ensure_user_tables(db_path)
    message = None

    if request.method == "POST":
        action = request.form.get("action")
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        with sqlite3.connect(str(db_path)) as conn:
            if action == "register" and email and password:
                try:
                    conn.execute(
                        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                        (email, generate_password_hash(password)),
                    )
                    conn.commit()
                    user_id = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
                    session["user_id"] = user_id
                    migrate_saved_lists(db_path, visitor_id, user_id)
                    record_event(db_path, f"user:{user_id}", "account_register", {"email": email})
                    return redirect(url_for("account.account_page"))
                except sqlite3.IntegrityError:
                    message = "Такой email уже зарегистрирован."
            elif action == "login" and email and password:
                row = conn.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
                if row and check_password_hash(row[1], password):
                    session["user_id"] = row[0]
                    migrate_saved_lists(db_path, visitor_id, row[0])
                    record_event(db_path, f"user:{row[0]}", "account_login", {"email": email})
                    return redirect(url_for("account.account_page"))
                message = "Неверный email или пароль."
            elif action == "save_weights" and session.get("user_id"):
                profile_weights = {
                    "score_weights": {
                        "value": float(request.form.get("weight_value", 30) or 30),
                        "transport": float(request.form.get("weight_transport", 25) or 25),
                        "infra": float(request.form.get("weight_infra", 20) or 20),
                        "fit": float(request.form.get("weight_fit", 15) or 15),
                        "district_bonus": float(request.form.get("weight_district_bonus", 10) or 10),
                    },
                    "district_score_weights": {
                        "object": float(request.form.get("district_weight_object", 35) or 35),
                        "transport": float(request.form.get("district_weight_transport", 20) or 20),
                        "infra": float(request.form.get("district_weight_infra", 20) or 20),
                        "family": float(request.form.get("district_weight_family", 15) or 15),
                        "investment": float(request.form.get("district_weight_investment", 10) or 10),
                    },
                }
                conn.execute(
                    "UPDATE users SET profile_weights = ? WHERE id = ?",
                    (json.dumps(profile_weights, ensure_ascii=False), session.get("user_id")),
                )
                conn.commit()
                record_event(db_path, f"user:{session.get('user_id')}", "weights_update", profile_weights)
                return redirect(url_for("account.account_page"))

    owner = owner_key(visitor_id)
    current_weights = load_user_weights(db_path)
    base_context = build_page_context(form=None, db_path=db_path, user_weights=None)
    with sqlite3.connect(str(db_path)) as conn:
        user_row = None
        if session.get("user_id"):
            user_row = conn.execute(
                "SELECT id, email, profile_weights, created_at FROM users WHERE id = ?",
                (session.get("user_id"),),
            ).fetchone()
        events = conn.execute(
            "SELECT event_type, payload, created_at FROM user_events WHERE owner_key = ? ORDER BY created_at DESC, id DESC LIMIT 12",
            (owner,),
        ).fetchall()
        reports = conn.execute(
            "SELECT token, report_type, created_at FROM report_shares WHERE owner_key = ? ORDER BY created_at DESC, id DESC LIMIT 10",
            (owner,),
        ).fetchall()
        lists = conn.execute(
            "SELECT listing_id, listing_key, list_type, created_at FROM saved_lists WHERE visitor_id = ? ORDER BY created_at DESC, id DESC LIMIT 20",
            (owner,),
        ).fetchall()
    weights = json.loads(user_row[2]) if user_row and user_row[2] else None
    saved_lists_payload = load_saved_lists(db_path, visitor_id)
    favorite_ids = sorted(saved_lists_payload.get("favorite", set()))
    shortlist_ids = sorted(saved_lists_payload.get("shortlist", set()))
    compare_ids = sorted(saved_lists_payload.get("compare", set()))
    preview_context = build_page_context(form=None, db_path=db_path, user_weights=current_weights)
    favorite_cards = _cards_by_ids(preview_context, favorite_ids[:6])
    shortlist_cards = _cards_by_ids(preview_context, shortlist_ids[:6])
    compare_cards = _cards_by_ids(preview_context, compare_ids[:2])
    compare_dashboard = build_compare_dashboard(compare_cards)
    district_preview = build_before_after_ranking(base_context, preview_context)
    dashboard_stats = {
        "favorites": len(favorite_ids),
        "shortlist": len(shortlist_ids),
        "compare": len(compare_ids),
        "reports": len(reports),
        "events": len(events),
    }
    response = make_response(
        render_template(
            "account.html",
            user=user_row,
            events=events,
            reports=reports,
            saved_items=lists,
            weights=weights,
            message=message,
            dashboard_stats=dashboard_stats,
            favorite_cards=favorite_cards,
            shortlist_cards=shortlist_cards,
            compare_cards=compare_cards,
            preview_shortlist=preview_context.get("shortlist", [])[:4],
            preview_pool=preview_context.get("listing_cards", {}).get("items", [])[:24],
            baseline_shortlist=base_context.get("shortlist", [])[:4],
            compare_dashboard=compare_dashboard,
            district_preview=district_preview,
        )
    )
    return set_visitor_cookie(response, visitor_id)


@account_bp.route("/logout", methods=["POST"], endpoint="logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("account.account_page"))
