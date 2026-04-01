from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from backend.DataFetcher import refresh_database
from backend.DataFetcher import DataFetcher
from backend.config import DEFAULT_DB_PATH, resolve_path
from main.app import create_app


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SAMPLE_SOURCE = PROJECT_ROOT / "sample_data" / "sample_listings.html"


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _default_source() -> str:
    return "test://default"


def _resolve_db_path(db_path: str | None) -> Path:
    return resolve_path(db_path or str(DEFAULT_DB_PATH))


def _database_has_records(db_path: Path) -> bool:
    try:
        return DataFetcher(db_path=str(db_path)).has_any_listings()
    except sqlite3.Error:
        return False


def _bootstrap_database(db_path: Path, source: str | None, reset: bool) -> None:
    effective_source = source or _default_source()
    refresh_database(source=effective_source, db_path=str(db_path), reset=reset)
    print(f"[run_project] База подготовлена: {db_path}")
    print(f"[run_project] Источник данных: {effective_source}")


def _ensure_runtime_database(db_path: Path, source: str | None) -> None:
    effective_source = source or _default_source()
    changed = DataFetcher(source=effective_source, db_path=str(db_path)).ensure_runtime_database(
        source=effective_source,
        bootstrap_if_empty=True,
    )
    if changed:
        print(f"[run_project] Выполнена проверка совместимости/автопочинка БД: {db_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Запускает Flask-приложение и при необходимости подготавливает базу данных."
    )
    parser.add_argument(
        "--host",
        default=os.getenv("FLASK_HOST", "127.0.0.1"),
        help="Хост веб-сервера. По умолчанию берётся из FLASK_HOST или используется 127.0.0.1.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("FLASK_PORT", "5000")),
        help="Порт веб-сервера. По умолчанию берётся из FLASK_PORT или используется 5000.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=_env_flag("FLASK_DEBUG", False),
        help="Запустить Flask в debug-режиме.",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Запустить приложение через waitress вместо встроенного Flask-сервера.",
    )
    parser.add_argument(
        "--db-path",
        default=os.getenv("MEPHI_DB_PATH"),
        help="Путь к SQLite-базе. По умолчанию берётся из MEPHI_DB_PATH или data.db.",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Источник для первичной загрузки данных: HTML-файл, URL или test://default.",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Пересоздать таблицу listings и заново загрузить данные перед стартом.",
    )
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Не выполнять автоматическую инициализацию/загрузку данных перед запуском.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    db_path = _resolve_db_path(args.db_path)

    if args.skip_bootstrap:
        print(f"[run_project] Автоподготовка базы пропущена. Используется: {db_path}")
    else:
        _ensure_runtime_database(db_path, args.source)
        should_bootstrap = args.reset_db or not _database_has_records(db_path)
        if should_bootstrap:
            _bootstrap_database(db_path, args.source, reset=True)
        else:
            print(f"[run_project] Используется существующая база: {db_path}")

    app = create_app(
        {
            "DB_PATH": str(db_path),
            "TESTING": _env_flag("MEPHI_TESTING", False),
        }
    )

    if args.production:
        from waitress import serve

        print(f"[run_project] Production-режим: http://{args.host}:{args.port}")
        serve(app, host=args.host, port=args.port)
        return

    print(f"[run_project] Development-режим: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
