from __future__ import annotations

import argparse
import logging

from backend.DataFetcher import DataFetcher, refresh_database
from backend.config import AppConfig, DEFAULT_DB_PATH, DEFAULT_RUNTIME_SOURCE, resolve_path
from backend.dataset_tools import clean_dataset_file, headers_are_compatible, merge_dataset_files, read_csv_rows, write_csv_rows


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

    geocode_parser = subparsers.add_parser("geocode-csv", help="Постепенно проставить точные координаты в CSV через remote geocoding.")
    geocode_parser.add_argument("--path", default=str(DEFAULT_RUNTIME_SOURCE), help="CSV-файл для enrichment.")
    geocode_parser.add_argument("--limit", type=int, default=25, help="Сколько строк обрабатывать за один запуск.")
    geocode_parser.add_argument("--pause", type=float, default=1.2, help="Минимальная задержка между remote-запросами.")
    geocode_parser.add_argument("--force", action="store_true", help="Перезапрашивать координаты даже если lat/lon уже заполнены.")

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


def _geocode_csv_rows(path: str, limit: int, pause: float, force: bool) -> tuple[int, int, int]:
    rows = read_csv_rows(path)
    fetcher = DataFetcher(
        source=path,
        config=AppConfig(remote_geocoding_enabled=True, geocoder_min_delay=max(float(pause), 0.0)),
    )
    updated = 0
    skipped = 0
    blocked = 0
    for row in rows:
        if updated >= max(limit, 0):
            break
        has_coordinates = bool(str(row.get("lat") or "").strip() and str(row.get("lon") or "").strip())
        if has_coordinates and not force:
            skipped += 1
            continue
        address = str(row.get("addres") or row.get("address") or "").strip()
        district = str(row.get("district") or "").strip()
        if not address or not district:
            skipped += 1
            continue
        geocoded = fetcher._request_remote_geocoder(address, district)
        if not fetcher._remote_geocoder_available() and not geocoded:
            blocked += 1
            break
        if not geocoded:
            skipped += 1
            continue
        row["lat"] = f"{float(geocoded.get('lat') or 0):.6f}"
        row["lon"] = f"{float(geocoded.get('lon') or 0):.6f}"
        row["geocode_status"] = str(geocoded.get("geocode_status") or "geocoded")
        row["geocode_source"] = str(geocoded.get("geocode_source") or "nominatim")
        row["geocode_confidence"] = str(geocoded.get("geocode_confidence") or "")
        updated += 1
    write_csv_rows(path, rows)
    remaining = sum(1 for row in rows if not (str(row.get("lat") or "").strip() and str(row.get("lon") or "").strip()))
    return updated, skipped + blocked, remaining


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

    if args.command == "geocode-csv":
        _validate_csv_headers(args.path)
        updated, skipped, remaining = _geocode_csv_rows(args.path, args.limit, args.pause, args.force)
        print(f"[manage_data] geocoded -> {args.path}")
        print(f"[manage_data] updated rows: {updated}")
        print(f"[manage_data] skipped rows: {skipped}")
        print(f"[manage_data] remaining without lat/lon: {remaining}")
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
