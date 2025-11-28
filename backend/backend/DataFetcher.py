import requests
from bs4 import BeautifulSoup
import sqlite3
import os
import chardet
from queries import CREATE_TABLE_LISTINGS, INSERT_LISTING


class DataFetcher:
    def __init__(self, source, db_path="data.db"):
        self.source = source
        self.db_path = db_path
        #проверяем, является ли источник локальным файлом
        self.is_local_file = os.path.isfile(source)

    def detect_encoding(self, file_path):
        """Определяет кодировку файла"""
        # открываем файл в бинарном режиме
        with open(file_path, 'rb') as file:
            result = chardet.detect(file.read())
            encoding = result['encoding'] or 'utf-8'
            print(f"Определена кодировка: {encoding} (уверенность: {result['confidence']:.2f})")
            return encoding

    def fetch(self):
        """Читает локальный файл или скачивает страницу"""
        if self.is_local_file:
            # обработка HTML-файла
            print(f"Читаю локальный файл: {self.source}")
            encoding = self.detect_encoding(self.source)
            try:
                with open(self.source, 'r', encoding=encoding) as file:
                    content = file.read()
                    print(f"Файл успешно прочитан, размер: {len(content)} символов")
                    return content
            except Exception as e:
                print(f"Ошибка при чтении файла: {e}")
                return None
        else:
            # загрузка страницы по url
            print(f"Загружаю страницу: {self.source}")
            try:
                # отправляем get-запрос с заголовком User-Agent, чтобы имитировать браузер
                response = requests.get(self.source, headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code == 200:
                    print(f"Страница загружена, размер: {len(response.text)} символов")
                    return response.text
                # если статус не 200 - выводим код ошибки
                print(f"Ошибка при загрузке: {response.status_code}")
            except Exception as e:
                # обработка остальных ошибок (например, нет интернета)
                print(f"Ошибка при запросе: {e}")
            return None

    def parse(self, html):
        """Извлекает данные из HTML"""
        # создаём BeautifulSoup для парсинга
        soup = BeautifulSoup(html, "html.parser")
        listings = []

        #ищем все блоки объявлений с классом "listing-item"
        for item in soup.find_all("div", class_="listing-item"):
            # внутри каждого блока ищем цену и адрес
            price_span = item.find("span", class_="price")
            address_span = item.find("span", class_="address")
            # если оба элемента найдены - добавляем объявление в список
            listing_data = {
                "address": self.clean_text(address_span.get_text()) if address_span else "",
                "price": self.clean_text(price_span.get_text()) if price_span else "",
                "total_meters": "", # нужно заполнить
                "rooms_count": "",
                "floor": "",
                "floors_count": "",
                "object_type": "",
                "house_material_type": "",
                "year_of_construction": "",
                "district": "",
                "underground": "",
                "url": "" # нужно заполнить
            }

            # проверяем, есть ли хотя бы основные данные
            if listing_data["price"] or listing_data["address"]: # пример "основных данных", изменить позже
                listings.append(listing_data)
                print(f"Найдено объявление: {listing_data['address']} - {listing_data['price']}")

        print(f"Всего найдено {len(listings)} объявлений")
        return listings

    @staticmethod
    def clean_text(text):
        """Очищает текст от лишних пробелов и символов"""
        # приводим к нормальной форме (без лишних пробелов/переносов)
        return ' '.join(text.split()).strip() if text else ""

    def save_to_db(self, listings):
        """Сохраняет данные в SQLite"""
        if not listings:
            print("Нет данных для сохранения")
            return
        # подключаемся к бд
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        # создаем таблицу, если она ещё не существует
        cur.execute(CREATE_TABLE_LISTINGS)
        # вставляем каждое объявление в таблицу
        for item in listings:
            cur.execute(
                INSERT_LISTING,
                (
                    item["address"],
                    item["price"],
                    item["total_meters"],
                    item["rooms_count"],
                    item["floor"],
                    item["floors_count"],
                    item["object_type"],
                    item["house_material_type"],
                    item["year_of_construction"],
                    item["district"],
                    item["underground"],
                    item["url"]
                    # created_at заполнится автоматом
                )
            )
        # фиксируем изменения и закрываем соединение
        conn.commit()
        conn.close()
        print(f"Сохранено {len(listings)} записей в базу {self.db_path}")

    def run(self):
        """Полный цикл: скачать - распарсить - сохранить"""
        # получаем HTML-контент (из файла или сети)
        html = self.fetch()
        if html:
            # парсим html и извлекаем объявления
            data = self.parse(html)
            if data:
                # сохраняем данные в базу
                self.save_to_db(data)
            else:
                print("Не найдено данных для сохранения.")
        else:
            print("Не удалось получить HTML-контент")


# точка входа в программу
if __name__ == "__main__":
    # путь к локальному HTML-файлу с сохранённой страницей
    file_path = r"123321"
    if os.path.exists(file_path):
        print(f"Файл найден: {file_path}")
        print(f"Размер файла: {os.path.getsize(file_path)} байт")
        # создаём объект парсера с указанием локального файла
        fetcher = DataFetcher(file_path)
        # запускаем полный цикл обработки
        fetcher.run()

        # выводим содержимое базы данных для проверки
        print("\nСодержимое базы данных:")
        conn = sqlite3.connect("data.db")
        for row in conn.execute("SELECT * FROM listings"):
            print(f"  ID: {row[0]}, Адрес: {row[1]}, Цена: {row[2]}")
        conn.close()
    else:
        print(f"Файл не найден: {file_path}")