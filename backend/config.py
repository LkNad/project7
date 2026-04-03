from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data.db"
DEFAULT_TEST_DATASET_NAME = "default"
DEFAULT_TEST_SOURCE_NAME = "test-dataset"
DEFAULT_RUNTIME_SOURCE = BASE_DIR / "sample_data" / "city_price_map_requests.csv"


@dataclass(slots=True)
class AppConfig:
    db_path: Path = DEFAULT_DB_PATH
    request_timeout: float = 10.0
    test_dataset_name: str = DEFAULT_TEST_DATASET_NAME
    remote_geocoding_enabled: bool = False
    geocoder_endpoint: str = "https://nominatim.openstreetmap.org/search"
    geocoder_email: str = ""
    geocoder_min_delay: float = 1.0
    yandex_geocoder_key: str = ""
    yandex_geocoder_endpoint: str = "https://geocode-maps.yandex.ru/1.x/"

    @staticmethod
    def _env_flag(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def from_env(cls) -> "AppConfig":
        db_path = Path(os.getenv("MEPHI_DB_PATH", str(DEFAULT_DB_PATH)))
        request_timeout = float(os.getenv("MEPHI_REQUEST_TIMEOUT", "10"))
        test_dataset_name = os.getenv("MEPHI_TEST_DATASET", DEFAULT_TEST_DATASET_NAME)
        return cls(
            db_path=db_path,
            request_timeout=request_timeout,
            test_dataset_name=test_dataset_name,
            remote_geocoding_enabled=cls._env_flag("MEPHI_REMOTE_GEOCODING", True),
            geocoder_endpoint=os.getenv("MEPHI_GEOCODER_ENDPOINT", "https://nominatim.openstreetmap.org/search"),
            geocoder_email=os.getenv("MEPHI_GEOCODER_EMAIL", ""),
            geocoder_min_delay=float(os.getenv("MEPHI_GEOCODER_MIN_DELAY", "1.0")),
            yandex_geocoder_key=os.getenv("MEPHI_YANDEX_GEOCODER_KEY", ""),
            yandex_geocoder_endpoint=os.getenv("MEPHI_YANDEX_GEOCODER_ENDPOINT", "https://geocode-maps.yandex.ru/1.x/"),
        )


def resolve_path(path: str | os.PathLike[str] | None) -> Path:
    if path in (None, ""):
        return DEFAULT_DB_PATH

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return BASE_DIR / candidate
