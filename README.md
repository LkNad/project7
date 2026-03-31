# Аналитика рынка недвижимости

Веб-приложение на Flask для импорта, хранения, фильтрации и визуального просмотра объявлений о недвижимости. Проект использует единую SQLite-схему, stateless-подход в веб-слое и воспроизводимый поток импорта данных из HTML, URL или встроенного тестового набора.

## Возможности

- импорт объявлений из локального HTML-файла, URL или встроенного тестового датасета;
- хранение данных в SQLite по единой схеме [`listings`](backend/queries.py);
- фильтрация по цене, району и числу комнат;
- визуализации в виде столбчатой, круговой, линейной диаграммы и таблицы;
- поставляемые примеры данных и автоматические тесты на [`pytest`](requirements.txt);
- запуск в development через Flask и в production через [`waitress`](requirements.txt).

## Структура каталогов

- [`app.py`](app.py) — WSGI entry point и локальный запуск Flask;
- [`run_project.py`](run_project.py) — основной скрипт запуска приложения с автоподготовкой базы данных;
- [`backend/`](backend/) — импорт, схема БД, модели и SQL-запросы;
- [`frontend/`](frontend/) — фильтрация, подготовка контекста и шаблоны UI;
- [`main/`](main/) — фабрика Flask-приложения;
- [`tests/`](tests/) — автоматические тесты и фикстуры;
- [`sample_data/`](sample_data/) — поставляемые примеры данных для импорта и демонстрации.

## Требования

- Python 3.11+;
- Windows, Linux или macOS;
- доступ к установке зависимостей из [`requirements.txt`](requirements.txt).

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Конфигурация

Поддерживаются переменные окружения:

- `MEPHI_DB_PATH` — путь к SQLite-файлу базы данных;
- `MEPHI_REQUEST_TIMEOUT` — таймаут HTTP-запроса при импорте;
- `MEPHI_TEST_DATASET` — имя встроенного тестового набора;
- `FLASK_HOST` — адрес Flask-сервера;
- `FLASK_PORT` — порт Flask-сервера;
- `FLASK_DEBUG` — режим отладки (`1`/`true` для включения);
- `MEPHI_TESTING` — внутренний флаг тестового запуска.

Если `MEPHI_DB_PATH` не задан, используется [`data.db`](data.db).

## Инициализация и импорт данных

Проект поддерживает импорт через [`backend.DataFetcher`](backend/DataFetcher.py).

### Встроенный тестовый набор

```bash
python -c "from backend.DataFetcher import refresh_database; refresh_database(source='test://default', reset=True)"
```

### Импорт из поставляемого HTML-примера

```bash
python -c "from backend.DataFetcher import refresh_database; refresh_database(source='sample_data/sample_listings.html', reset=True)"
```

### Импорт из URL

```bash
python -c "from backend.DataFetcher import refresh_database; refresh_database(source='https://example.test/listings')"
```

После импорта данные попадают в таблицу [`listings`](backend/queries.py).

## Запуск приложения

### Development-режим

Рекомендуемый способ запуска проекта:

```bash
python run_project.py
```

Скрипт [`run_project.py`](run_project.py) автоматически проверяет SQLite-базу и, если она пустая или отсутствует, загружает стартовые данные из [`sample_data/sample_listings.html`](sample_data/sample_listings.html).

По умолчанию приложение стартует на `127.0.0.1:5000`. При необходимости:

```bash
python run_project.py --host 0.0.0.0 --port 5000 --debug
```

Принудительно пересоздать таблицу и заново загрузить данные:

```bash
python run_project.py --reset-db
```

### Production-режим через Waitress

Так как в проекте уже используется [`waitress`](requirements.txt), production-запуск рекомендуется выполнять через единый скрипт:

```bash
python run_project.py --production --host 0.0.0.0 --port 5000
```

При работе с альтернативной БД:

```bash
python run_project.py --production --db-path sample_data/demo.db --source sample_data/sample_listings.html
```

## Тестирование

Автотесты покрывают:

- парсинг HTML и встроенного набора в [`backend/DataFetcher.py`](backend/DataFetcher.py);
- фильтрацию и формирование контекста в [`frontend/filters.py`](frontend/filters.py);
- интеграцию главной страницы [`index()`](main/app.py:24);
- согласованность схемы БД, чтение данных и сценарии пустой/тестовой базы.

Запуск всех тестов:

```bash
pytest -q
```

Запуск только интеграционных тестов Flask:

```bash
pytest -q tests/test_app.py
```

## Сценарии использования

### 1. Подготовить демонстрационную БД

```bash
python -c "from backend.DataFetcher import refresh_database; refresh_database(source='sample_data/sample_listings.html', db_path='sample_data/demo.db', reset=True)"
```

### 2. Запустить приложение на этой БД

```bash
set MEPHI_DB_PATH=sample_data/demo.db && python app.py
```

### 3. Проверить UI

- открыть главную страницу;
- убедиться, что отображаются карточки, таблица и сводка;
- применить фильтры по цене, району и комнатам;
- при пустой базе увидеть корректное сообщение о пустых данных.

## Поставляемые артефакты данных

- [`sample_data/sample_listings.html`](sample_data/sample_listings.html) — воспроизводимый HTML-пример для импорта;
- [`tests/fixtures/sample_listings.html`](tests/fixtures/sample_listings.html) — тестовая HTML-фикстура;
- встроенный набор `test://default` в [`backend/DataFetcher.py`](backend/DataFetcher.py).

## Примечания по качеству поставки

- зависимости в [`requirements.txt`](requirements.txt) очищены от лишних пакетов;
- запуск приложения не привязан к debug-режиму по умолчанию;
- тесты работают на изолированных временных SQLite-базах;
- документация синхронизирована с текущей архитектурой проекта.
