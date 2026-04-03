from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import textwrap

from flask import abort, current_app, request, session

from backend.DataFetcher import DataFetcher
from backend.dataset_tools import read_dataset_metadata
from backend.config import DEFAULT_RUNTIME_SOURCE
from frontend.filters import build_page_context


LOGGER = logging.getLogger(__name__)
VISITOR_COOKIE = "mephi_visitor_id"
CSRF_SESSION_KEY = "_csrf_token"


def _db_path(db_path: str | None = None) -> str:
    return str(db_path or current_app.config.get("DB_PATH"))


def stable_listing_key(address, district, price, rooms):
    address_value = " ".join(str(address or "").lower().split())
    district_value = " ".join(str(district or "").lower().split())
    price_value = str(price or 0).replace(" ", "").replace(",", ".")
    try:
        rounded_price = round(float(price_value), -4)
    except (TypeError, ValueError):
        rounded_price = 0
    try:
        rooms_value = int(str(rooms or 0).split()[0])
    except (TypeError, ValueError, IndexError):
        rooms_value = 0
    return f"{address_value}|{district_value}|{rounded_price}|{rooms_value}"


def fetch_listing_record(conn: sqlite3.Connection, listing_id: int):
    row = conn.execute(
        "SELECT id, address, district, price, rooms FROM listings WHERE id = ?",
        (listing_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "address": row[1],
        "district": row[2],
        "price": row[3],
        "rooms": row[4],
        "listing_key": stable_listing_key(row[1], row[2], row[3], row[4]),
    }


def set_visitor_cookie(response, visitor_id: str):
    response.set_cookie(
        VISITOR_COOKIE,
        visitor_id,
        max_age=60 * 60 * 24 * 180,
        samesite="Lax",
        httponly=True,
        secure=bool(current_app.config.get("SESSION_COOKIE_SECURE")),
    )
    return response


def csrf_token() -> str:
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def validate_csrf() -> None:
    expected_token = session.get(CSRF_SESSION_KEY)
    provided_token = request.headers.get("X-CSRF-Token") or request.form.get("_csrf_token")
    if not expected_token or not provided_token or not secrets.compare_digest(expected_token, provided_token):
        abort(400, description="CSRF validation failed")


def ensure_user_tables(db_path: str | None = None):
    with sqlite3.connect(_db_path(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                profile_weights TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_key TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS report_shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                owner_key TEXT NOT NULL,
                report_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "profile_weights" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN profile_weights TEXT DEFAULT ''")
        conn.commit()


def ensure_saved_lists_table(db_path: str | None = None):
    db_value = _db_path(db_path)
    with sqlite3.connect(db_value) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id TEXT NOT NULL,
                listing_id INTEGER NOT NULL,
                listing_key TEXT NOT NULL DEFAULT '',
                list_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(visitor_id, listing_key, list_type)
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(saved_lists)").fetchall()}
        if "listing_key" not in columns:
            conn.execute("ALTER TABLE saved_lists RENAME TO saved_lists_legacy")
            conn.execute(
                """
                CREATE TABLE saved_lists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    visitor_id TEXT NOT NULL,
                    listing_id INTEGER NOT NULL,
                    listing_key TEXT NOT NULL DEFAULT '',
                    list_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(visitor_id, listing_key, list_type)
                )
                """
            )
            rows = conn.execute(
                "SELECT id, visitor_id, listing_id, list_type, created_at FROM saved_lists_legacy ORDER BY id ASC"
            ).fetchall()
            for row in rows:
                listing = fetch_listing_record(conn, row[2])
                if not listing:
                    continue
                conn.execute(
                    """
                    INSERT OR IGNORE INTO saved_lists (id, visitor_id, listing_id, listing_key, list_type, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (row[0], row[1], listing["id"], listing["listing_key"], row[3], row[4]),
                )
            conn.execute("DROP TABLE saved_lists_legacy")
        else:
            rows = conn.execute(
                "SELECT id, listing_id FROM saved_lists WHERE COALESCE(listing_key, '') = ''"
            ).fetchall()
            for row in rows:
                listing = fetch_listing_record(conn, row[1])
                if not listing:
                    continue
                conn.execute(
                    "UPDATE saved_lists SET listing_key = ?, listing_id = ? WHERE id = ?",
                    (listing["listing_key"], listing["id"], row[0]),
                )
        conn.commit()


def get_or_create_visitor_id() -> str:
    return request.cookies.get(VISITOR_COOKIE) or secrets.token_hex(16)


def owner_key(visitor_id: str | None = None) -> str:
    user_id = session.get("user_id")
    if user_id:
        return f"user:{user_id}"
    return f"visitor:{visitor_id or get_or_create_visitor_id()}"


def load_user_weights(db_path: str | None = None):
    user_id = session.get("user_id")
    if not user_id:
        return None
    ensure_user_tables(db_path)
    with sqlite3.connect(_db_path(db_path)) as conn:
        row = conn.execute("SELECT profile_weights FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or not row[0]:
        return None
    try:
        return json.loads(row[0])
    except (TypeError, ValueError):
        return None


def load_listing_cards_by_ids(db_path, listing_ids, user_weights=None):
    if not listing_ids:
        return []
    context = build_page_context(form=None, db_path=db_path, user_weights=user_weights)
    listing_map = {item.get("id"): item for item in context.get("listing_cards", {}).get("items", [])}
    return [listing_map[item_id] for item_id in listing_ids if item_id in listing_map]


def build_compare_dashboard(compare_cards):
    if len(compare_cards) < 2:
        return None
    left, right = compare_cards[0], compare_cards[1]
    left_score = float(left.get("scores", {}).get("object_score", 0))
    right_score = float(right.get("scores", {}).get("object_score", 0))
    winner = left if left_score >= right_score else right
    loser = right if winner is left else left
    return {
        "winner": winner,
        "loser": loser,
        "score_gap": round(abs(left_score - right_score), 1),
        "price_gap": round(abs(float(left.get("price") or 0) - float(right.get("price") or 0)), 0),
        "confidence_gap": abs(int(left.get("confidence_score") or 0) - int(right.get("confidence_score") or 0)),
        "summary": f"{winner.get('title')} выигрывает по итоговому score и выглядит убедительнее для текущего профиля.",
    }


def build_before_after_ranking(base_context, weighted_context):
    base_districts = base_context.get("districts", [])[:6]
    weighted_districts = weighted_context.get("districts", [])[:6]
    base_rank = {item.get("district"): index + 1 for index, item in enumerate(base_context.get("districts", []))}
    weighted_rank = {item.get("district"): index + 1 for index, item in enumerate(weighted_context.get("districts", []))}
    districts = []
    ordered_names = [item.get("district") for item in base_districts + weighted_districts]
    for district_name in list(dict.fromkeys(ordered_names))[:8]:
        districts.append(
            {
                "district": district_name,
                "base_rank": base_rank.get(district_name),
                "weighted_rank": weighted_rank.get(district_name),
                "delta": (base_rank.get(district_name) or 99) - (weighted_rank.get(district_name) or 99),
            }
        )
    return districts


def record_event(db_path, owner_key_value, event_type, payload):
    ensure_user_tables(db_path)
    with sqlite3.connect(_db_path(db_path)) as conn:
        conn.execute(
            "INSERT INTO user_events (owner_key, event_type, payload) VALUES (?, ?, ?)",
            (owner_key_value, event_type, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()


def migrate_saved_lists(db_path, visitor_id, user_id):
    visitor_key = f"visitor:{visitor_id}"
    user_key = f"user:{user_id}"
    ensure_saved_lists_table(db_path)
    with sqlite3.connect(_db_path(db_path)) as conn:
        rows = conn.execute(
            "SELECT listing_id, listing_key, list_type FROM saved_lists WHERE visitor_id = ?",
            (visitor_key,),
        ).fetchall()
        for listing_id, listing_key, list_type in rows:
            conn.execute(
                "INSERT OR IGNORE INTO saved_lists (visitor_id, listing_id, listing_key, list_type) VALUES (?, ?, ?, ?)",
                (user_key, listing_id, listing_key, list_type),
            )
        conn.execute("DELETE FROM saved_lists WHERE visitor_id = ?", (visitor_key,))
        conn.commit()


def _ascii_safe(value):
    return str(value or "").encode("ascii", "ignore").decode("ascii") or "n/a"


def build_simple_pdf(title, lines):
    safe_title = _ascii_safe(title)
    content_lines = [safe_title, ""] + [_ascii_safe(line) for line in lines]
    y = 780
    stream_lines = ["BT", "/F1 18 Tf", f"50 {y} Td ({safe_title}) Tj"]
    y -= 28
    stream_lines.extend(["/F1 11 Tf"])
    for line in content_lines[2:]:
        for chunk in textwrap.wrap(line, width=88) or [""]:
            stream_lines.append(f"1 0 0 1 50 {y} Tm ({chunk.replace('(', '[').replace(')', ']')}) Tj")
            y -= 16
            if y < 50:
                break
        if y < 50:
            break
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("latin-1", "ignore")
    objects = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj")
    objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj")
    objects.append(b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj")
    objects.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")
    objects.append(f"5 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1") + stream + b"\nendstream endobj")
    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj + b"\n"
    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode("latin-1")
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode("latin-1")
    pdf += f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("latin-1")
    return pdf


def build_report_pdf(report_type, created_at, payload):
    summary = [
        f"report type: {report_type}",
        f"created at: {created_at}",
        f"items: {len(payload)}",
    ]
    avg_trust = round(sum(float(item.get("source_trust_score") or 0) for item in payload) / len(payload), 1) if payload else 0
    avg_confidence = round(sum(float(item.get("confidence_score") or 0) for item in payload) / len(payload), 1) if payload else 0
    freshness = ", ".join(sorted({str(item.get("freshness_label") or "без даты") for item in payload})) if payload else "n/a"
    summary.extend([
        f"avg trust: {avg_trust}",
        f"avg confidence: {avg_confidence}",
        f"freshness mix: {freshness}",
        "",
        "items:",
    ])
    for item in payload:
        summary.append(
            f"{item.get('title')} | {item.get('district')} | {item.get('price_compact')} | trust {item.get('source_trust_score')} | confidence {item.get('confidence_score')} | {item.get('freshness_label')}"
        )
    return build_simple_pdf(f"Mephi {report_type} report", summary)


def load_saved_lists(db_path, visitor_id):
    ensure_saved_lists_table(db_path)
    ensure_user_tables(db_path)
    owner_key_value = owner_key(visitor_id)
    with sqlite3.connect(_db_path(db_path)) as conn:
        rows = conn.execute(
            "SELECT listing_id, listing_key, list_type FROM saved_lists WHERE visitor_id = ?",
            (owner_key_value,),
        ).fetchall()
        listing_rows = conn.execute("SELECT id, address, district, price, rooms FROM listings").fetchall()
    key_to_listing_id = {stable_listing_key(row[1], row[2], row[3], row[4]): row[0] for row in listing_rows}
    known_listing_ids = set(key_to_listing_id.values())
    payload = {"favorite": set(), "shortlist": set(), "compare": set()}
    for listing_id, listing_key, list_type in rows:
        resolved_listing_id = key_to_listing_id.get(listing_key or "") or listing_id
        if resolved_listing_id in known_listing_ids:
            payload.setdefault(list_type, set()).add(resolved_listing_id)
    return payload


def apply_saved_state(context, saved_lists):
    favorites = saved_lists.get("favorite", set())
    shortlist = saved_lists.get("shortlist", set())
    compare = saved_lists.get("compare", set())
    for item in context.get("listing_cards", {}).get("items", []):
        item["is_favorite"] = item.get("id") in favorites
        item["is_saved_shortlist"] = item.get("id") in shortlist
        item["is_in_compare"] = item.get("id") in compare
    for item in context.get("shortlist", []):
        item["is_favorite"] = item.get("id") in favorites
        item["is_saved_shortlist"] = item.get("id") in shortlist
    selected_listing = context.get("selected_listing")
    if selected_listing:
        selected_listing["is_favorite"] = selected_listing.get("id") in favorites
        selected_listing["is_saved_shortlist"] = selected_listing.get("id") in shortlist
        selected_listing["is_in_compare"] = selected_listing.get("id") in compare
    return context


def json_response(context):
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


def prepare_app_database(app) -> None:
    db_path = app.config.get("DB_PATH")
    DataFetcher(db_path=db_path).ensure_database_compatibility()
    ensure_user_tables(db_path)
    ensure_saved_lists_table(db_path)


def load_data_quality(db_path: str | None = None) -> dict[str, object]:
    dataset_path = current_app.config.get("DEFAULT_RUNTIME_SOURCE") or str(DEFAULT_RUNTIME_SOURCE)
    metadata = read_dataset_metadata(dataset_path)
    with sqlite3.connect(_db_path(db_path)) as conn:
        listing_count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        nominatim_count = conn.execute("SELECT COUNT(*) FROM listings WHERE LOWER(COALESCE(geocode_source, '')) = 'nominatim'").fetchone()[0]
        fallback_count = conn.execute("SELECT COUNT(*) FROM listings WHERE LOWER(COALESCE(geocode_source, '')) = 'deterministic-local'").fetchone()[0]
        provided_count = conn.execute("SELECT COUNT(*) FROM listings WHERE LOWER(COALESCE(geocode_source, '')) IN ('provided', 'source-payload')").fetchone()[0]
    raw_rows = int(metadata.get("raw_rows", listing_count)) if metadata else listing_count
    dropped_rows = int(metadata.get("dropped_rows", 0)) if metadata else 0
    return {
        "dataset_path": dataset_path,
        "raw_rows": raw_rows,
        "listing_count": listing_count,
        "dropped_rows": dropped_rows,
        "nominatim_count": nominatim_count,
        "fallback_count": fallback_count,
        "provided_count": provided_count,
        "metadata": metadata,
    }
