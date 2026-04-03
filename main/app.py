from __future__ import annotations

import logging
import os
import secrets
import sys
import threading

from flask import Flask, request

from backend.DataFetcher import DataFetcher
from backend.config import AppConfig, DEFAULT_DB_PATH, DEFAULT_RUNTIME_SOURCE
from main.blueprints import account_bp, api_bp, reports_bp, workspace_bp
from main.web import csrf_token, prepare_app_database, validate_csrf


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "frontend", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "frontend", "static")
LOGGER = logging.getLogger(__name__)


def _start_runtime_bootstrap(app: Flask) -> None:
    if not app.config.get("AUTO_BOOTSTRAP_RUNTIME_DATASET") or app.config.get("TESTING"):
        return

    bootstrap_source = app.config.get("DEFAULT_RUNTIME_SOURCE", "test://default")
    app.config["BOOTSTRAP_STATUS"] = {"state": "running", "source": bootstrap_source, "error": ""}

    def _bootstrap_runtime_dataset():
        try:
            LOGGER.info("Фоновая инициализация runtime-данных запущена: %s", bootstrap_source)
            changed = DataFetcher(
                source=bootstrap_source,
                db_path=app.config.get("DB_PATH"),
            ).ensure_runtime_database(
                source=bootstrap_source,
                bootstrap_if_empty=True,
            )
            app.config["BOOTSTRAP_STATUS"] = {
                "state": "ready",
                "source": bootstrap_source,
                "error": "",
                "changed": bool(changed),
            }
            LOGGER.info("Фоновая инициализация runtime-данных завершена")
        except Exception as error:
            app.config["BOOTSTRAP_STATUS"] = {
                "state": "error",
                "source": bootstrap_source,
                "error": str(error),
            }
            LOGGER.exception("Ошибка фоновой инициализации runtime-данных")

    threading.Thread(target=_bootstrap_runtime_dataset, daemon=True, name="runtime-bootstrap").start()


def create_app(test_config=None):
    app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
    configured_secret = os.getenv("MEPHI_SECRET_KEY") or ("test-secret" if (test_config or {}).get("TESTING") else secrets.token_urlsafe(32))
    if not os.getenv("MEPHI_SECRET_KEY") and not (test_config or {}).get("TESTING"):
        LOGGER.warning("MEPHI_SECRET_KEY не задан, используется одноразовый секрет процесса")

    app.config.from_mapping(
        SECRET_KEY=configured_secret,
        DB_PATH=str(DEFAULT_DB_PATH),
        TESTING=False,
        AUTO_BOOTSTRAP_RUNTIME_DATASET=True,
        DEFAULT_RUNTIME_SOURCE=str(DEFAULT_RUNTIME_SOURCE),
        REMOTE_GEOCODING_ENABLED=AppConfig.from_env().remote_geocoding_enabled,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("MEPHI_SESSION_COOKIE_SECURE", "0").strip().lower() in {"1", "true", "yes", "on"},
    )
    if test_config:
        app.config.update(test_config)
    if app.config.get("TESTING") and (not test_config or "REMOTE_GEOCODING_ENABLED" not in test_config):
        app.config["REMOTE_GEOCODING_ENABLED"] = False

    prepare_app_database(app)
    app.config.setdefault(
        "BOOTSTRAP_STATUS",
        {
            "state": "idle",
            "source": app.config.get("DEFAULT_RUNTIME_SOURCE", "test://default"),
            "error": "",
        },
    )
    _start_runtime_bootstrap(app)

    @app.before_request
    def _protect_against_csrf():
        if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            csrf_token()
            return None
        validate_csrf()
        return None

    @app.context_processor
    def _inject_template_security_context():
        return {"csrf_token": csrf_token}

    app.register_blueprint(workspace_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(api_bp)
    return app


app = None if os.getenv("MEPHI_SKIP_EAGER_APP", "0") == "1" or "pytest" in sys.modules else create_app()
