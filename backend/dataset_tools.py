from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Mapping, Sequence


CSV_FIELDNAMES = [
    "id",
    "title",
    "addres",
    "district",
    "lat",
    "lon",
    "geocode_status",
    "geocode_source",
    "geocode_confidence",
    "price",
    "area",
    "rooms",
    "floor",
    "total_floors",
    "source_url",
    "image_url",
    "description",
    "deal_type",
    "building_type",
    "metro_station",
    "metro_time_minutes",
    "created_at",
]

REQUIRED_INPUT_HEADERS = {"title", "addres", "district", "price", "area", "source_url"}
HEADER_ALIASES = {
    "listing_id": "id",
    "address": "addres",
    "url": "source_url",
    "metro_time_min": "metro_time_minutes",
}


def _string(value) -> str:
    return str(value or "").strip()


def metadata_path_for(path: str | Path) -> Path:
    target = Path(path)
    return target.with_name(f"{target.stem}.metadata.json")


def _normalize_headers(headers) -> set[str]:
    normalized = set()
    for header in headers or []:
        value = _string(header)
        if not value:
            continue
        normalized.add(HEADER_ALIASES.get(value, value))
    return normalized


def headers_are_compatible(headers) -> bool:
    return REQUIRED_INPUT_HEADERS.issubset(_normalize_headers(headers))


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_row(row: Mapping[str, object], row_id: int) -> dict[str, str]:
    return {
        "id": str(row_id),
        "title": _string(row.get("title")),
        "addres": _string(row.get("addres") or row.get("address")),
        "district": _string(row.get("district")),
        "lat": _string(row.get("lat") or row.get("latitude") or row.get("geo_lat")),
        "lon": _string(row.get("lon") or row.get("longitude") or row.get("geo_lon")),
        "geocode_status": _string(row.get("geocode_status")),
        "geocode_source": _string(row.get("geocode_source")),
        "geocode_confidence": _string(row.get("geocode_confidence")),
        "price": _string(row.get("price")),
        "area": _string(row.get("area")),
        "rooms": _string(row.get("rooms")),
        "floor": _string(row.get("floor")),
        "total_floors": _string(row.get("total_floors")),
        "source_url": _string(row.get("source_url") or row.get("url")),
        "image_url": _string(row.get("image_url")),
        "description": _string(row.get("description")),
        "deal_type": _string(row.get("deal_type")),
        "building_type": _string(row.get("building_type")),
        "metro_station": _string(row.get("metro_station")),
        "metro_time_minutes": _string(row.get("metro_time_minutes") or row.get("metro_time_min")),
        "created_at": _string(row.get("created_at")),
    }


def clean_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, str]]:
    cleaned = []
    seen_urls = set()
    for row in rows:
        normalized = normalize_row(row, len(cleaned))
        source_url = normalized["source_url"]
        if not normalized["addres"] or not normalized["district"] or not source_url:
            continue
        if not normalized["price"] or not normalized["area"]:
            continue
        if source_url in seen_urls:
            continue
        seen_urls.add(source_url)
        normalized["id"] = str(len(cleaned))
        cleaned.append(normalized)
    return cleaned


def dataset_quality_stats(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    seen_urls = set()
    duplicate_rows = 0
    incomplete_rows = 0
    valid_rows = 0
    for row in rows:
        normalized = normalize_row(row, 0)
        source_url = normalized["source_url"]
        is_incomplete = not normalized["addres"] or not normalized["district"] or not source_url or not normalized["price"] or not normalized["area"]
        if is_incomplete:
            incomplete_rows += 1
            continue
        if source_url in seen_urls:
            duplicate_rows += 1
            continue
        seen_urls.add(source_url)
        valid_rows += 1
    return {
        "raw_rows": len(rows),
        "valid_rows": valid_rows,
        "incomplete_rows": incomplete_rows,
        "duplicate_rows": duplicate_rows,
        "dropped_rows": incomplete_rows + duplicate_rows,
    }


def write_dataset_metadata(path: str | Path, stats: dict[str, int]) -> Path:
    metadata_path = metadata_path_for(path)
    previous = read_dataset_metadata(path)
    merged_stats = dict(stats)
    if previous:
        merged_stats["raw_rows"] = max(int(previous.get("raw_rows", 0)), int(stats.get("raw_rows", 0)))
        merged_stats["valid_rows"] = max(int(previous.get("valid_rows", 0)), int(stats.get("valid_rows", 0)))
        merged_stats["incomplete_rows"] = max(int(previous.get("incomplete_rows", 0)), int(stats.get("incomplete_rows", 0)))
        merged_stats["duplicate_rows"] = max(int(previous.get("duplicate_rows", 0)), int(stats.get("duplicate_rows", 0)))
        merged_stats["dropped_rows"] = max(int(previous.get("dropped_rows", 0)), int(stats.get("dropped_rows", 0)))
    metadata_path.write_text(json.dumps(merged_stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata_path


def read_dataset_metadata(path: str | Path) -> dict[str, int]:
    metadata_path = metadata_path_for(path)
    if not metadata_path.exists():
        return {}
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def merge_rows(base_rows: Sequence[Mapping[str, object]], extra_rows: Sequence[Mapping[str, object]]) -> list[dict[str, str]]:
    return clean_rows(list(base_rows) + list(extra_rows))


def write_csv_rows(path: str | Path, rows: Sequence[Mapping[str, object]]) -> Path:
    target = Path(path)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for index, row in enumerate(rows):
            writer.writerow(normalize_row(row, index))
    return target


def clean_dataset_file(path: str | Path) -> tuple[Path, int, int]:
    input_rows = read_csv_rows(path)
    stats = dataset_quality_stats(input_rows)
    cleaned = clean_rows(input_rows)
    write_csv_rows(path, cleaned)
    write_dataset_metadata(path, stats)
    return Path(path), len(input_rows), len(cleaned)


def merge_dataset_files(base_path: str | Path, extra_path: str | Path, output_path: str | Path | None = None) -> tuple[Path, int, int]:
    base_rows = read_csv_rows(base_path)
    extra_rows = read_csv_rows(extra_path)
    target = Path(output_path) if output_path else Path(base_path)
    merged_input = list(base_rows) + list(extra_rows)
    stats = dataset_quality_stats(merged_input)
    merged = clean_rows(merged_input)
    write_csv_rows(target, merged)
    write_dataset_metadata(target, stats)
    return target, len(base_rows) + len(extra_rows), len(merged)
