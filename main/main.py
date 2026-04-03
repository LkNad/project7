# main/main.py
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
if callable(stdout_reconfigure):
    stdout_reconfigure(encoding="utf-8")
if callable(stderr_reconfigure):
    stderr_reconfigure(encoding="utf-8")

os.environ.setdefault("MEPHI_SKIP_EAGER_APP", "1")

try:
    from main.app import create_app
except ModuleNotFoundError:
    from app import create_app


def _env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    _configure_logging()
    logger = logging.getLogger("main")

    db_path = os.getenv("MEPHI_DB_PATH", "data.db")
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = _env_flag("FLASK_DEBUG", False)
    testing = _env_flag("MEPHI_TESTING", False)

    logger.info("Запуск приложения. DB=%s host=%s port=%s", db_path, host, port)
    logger.info("Инициализация Flask и проверка runtime-данных...")

    try:
        app = create_app(
            {
                "DB_PATH": db_path,
                "TESTING": testing,
            }
        )
    except Exception:
        logger.exception("Ошибка во время инициализации приложения")
        raise

    logger.info("Инициализация завершена. Сервер поднимается на http://%s:%s", host, port)
    try:
        app.run(
            debug=debug,
            host=host,
            port=port,
        )
    except Exception:
        logger.exception("Ошибка во время запуска Flask-сервера")
        raise


if __name__ == '__main__':
    main()
