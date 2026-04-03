from __future__ import annotations

import json
import sqlite3

from flask import Blueprint, current_app, make_response, render_template

from main.web import build_report_pdf, ensure_user_tables


reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/report/<token>", methods=["GET"], endpoint="shared_report")
def shared_report(token):
    db_path = current_app.config.get("DB_PATH")
    ensure_user_tables(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute("SELECT report_type, payload, created_at FROM report_shares WHERE token = ?", (token,)).fetchone()
    if not row:
        return render_template("report.html", report=None), 404
    payload = json.loads(row[1])
    return render_template("report.html", report={"type": row[0], "created_at": row[2], "items": payload})


@reports_bp.route("/report/<token>.pdf", methods=["GET"], endpoint="shared_report_pdf")
def shared_report_pdf(token):
    db_path = current_app.config.get("DB_PATH")
    ensure_user_tables(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute("SELECT report_type, payload, created_at FROM report_shares WHERE token = ?", (token,)).fetchone()
    if not row:
        return ("Report not found", 404)
    payload = json.loads(row[1])
    pdf = build_report_pdf(row[0], row[2], payload)
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename=report-{token}.pdf"
    return response
