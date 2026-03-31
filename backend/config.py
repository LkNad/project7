from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data.db"
DEFAULT_TEST_DATASET_NAME = "default"
DEFAULT_TEST_SOURCE_NAME = "test-dataset"


@dataclass(slots=True)
class AppConfig:
    db_path: Path = DEFAULT_DB_PATH
    request_timeout: float = 10.0
    test_dataset_name: str = DEFAULT_TEST_DATASET_NAME

    @classmethod
    def from_env(cls) -> "AppConfig":
        db_path = Path(os.getenv("MEPHI_DB_PATH", str(DEFAULT_DB_PATH)))
        request_timeout = float(os.getenv("MEPHI_REQUEST_TIMEOUT", "10"))
        test_dataset_name = os.getenv("MEPHI_TEST_DATASET", DEFAULT_TEST_DATASET_NAME)
        return cls(
            db_path=db_path,
            request_timeout=request_timeout,
            test_dataset_name=test_dataset_name,
        )


def resolve_path(path: str | os.PathLike[str] | None) -> Path:
    if path in (None, ""):
        return DEFAULT_DB_PATH

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return BASE_DIR / candidate
