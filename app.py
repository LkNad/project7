import os

from main.app import create_app


def _env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


app = create_app(
    {
        "DB_PATH": os.getenv("MEPHI_DB_PATH", "data.db"),
        "TESTING": _env_flag("MEPHI_TESTING", False),
    }
)


if __name__ == "__main__":
    app.run(
        debug=_env_flag("FLASK_DEBUG", False),
        host=os.getenv("FLASK_HOST", "127.0.0.1"),
        port=int(os.getenv("FLASK_PORT", "5000")),
    )
