from __future__ import annotations

import argparse
import logging

from backend.DataFetcher import refresh_database
from backend.config import AppConfig, DEFAULT_DB_PATH, DEFAULT_RUNTIME_SOURCE, resolve_path
from backend.dataset_tools import clean_dataset_file, headers_are_compatible, merge_dataset_files, read_csv_rows


LOGGER = logging.getLogger("manage_data")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Утилиты для merge/clean/rebuild датасета и runtime-БД.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    merge_parser = subparsers.add_parser("merge-csv", help="Объединить базовый и внешний CSV с очисткой и дедупликацией.")
    merge_parser.add_argument("--base", default=str(DEFAULT_RUNTIME_SOURCE), help="Базовый CSV-файл проекта.")
    merge_parser.add_argument("--extra", required=True, help="Внешний CSV для добавления.")
    merge_parser.add_argument("--output", default=None, help="Куда записать результат. По умолчанию перезаписывает base.")

    clean_parser = subparsers.add_parser("clean-csv", help="Очистить CSV от неполных и дублирующихся строк.")
    clean_parser.add_argument("--path", default=str(DEFAULT_RUNTIME_SOURCE), help="CSV-файл для очистки.")

    rebuild_parser = subparsers.add_parser("rebuild-db", help="Явно пересобрать runtime-БД из CSV/HTML/test dataset.")
    rebuild_parser.add_argument("--source", default=str(DEFAULT_RUNTIME_SOURCE), help="Источник данных для rebuild.")
    rebuild_parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="Путь к SQLite-базе.")
    rebuild_parser.add_argument("--remote-geocoding", action="store_true", help="Разрешить remote geocoding для controlled refresh.")

    return parser


def _validate_csv_headers(path: str) -> None:
    rows = read_csv_rows(path)
    headers = rows[0].keys() if rows else []
    if not headers_are_compatible(headers):
        raise SystemExit(f"CSV {path} несовместим с ожидаемой схемой")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args()

    if args.command == "merge-csv":
        _validate_csv_headers(args.base)
        _validate_csv_headers(args.extra)
        target, raw_count, cleaned_count = merge_dataset_files(args.base, args.extra, args.output)
        print(f"[manage_data] merged -> {target}")
        print(f"[manage_data] raw rows: {raw_count}")
        print(f"[manage_data] cleaned rows: {cleaned_count}")
        return

    if args.command == "clean-csv":
        _validate_csv_headers(args.path)
        target, raw_count, cleaned_count = clean_dataset_file(args.path)
        print(f"[manage_data] cleaned -> {target}")
        print(f"[manage_data] raw rows: {raw_count}")
        print(f"[manage_data] cleaned rows: {cleaned_count}")
        return

    config = AppConfig(db_path=resolve_path(args.db_path), remote_geocoding_enabled=bool(args.remote_geocoding))
    rows = refresh_database(
        source=args.source,
        db_path=str(resolve_path(args.db_path)),
        reset=True,
        config=config,
    )
    print(f"[manage_data] rebuilt DB -> {resolve_path(args.db_path)}")
    print(f"[manage_data] source -> {args.source}")
    print(f"[manage_data] remote geocoding -> {config.remote_geocoding_enabled}")
    print(f"[manage_data] saved rows -> {len(rows)}")


if __name__ == "__main__":
    main()
