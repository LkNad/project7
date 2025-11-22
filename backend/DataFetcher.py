import requests
from bs4 import BeautifulSoup
import sqlite3
import os
import chardet

class DataFetcher:
    def __init__(self, source, db_path="data.db"):
        self.source = source
        self.db_path = db_path
        self.is_local_file = os.path.isfile(source)

    def detect_encoding(self, file_path):
        """Определяет кодировку файла"""
        with open(file_path, 'rb') as file:
            result = chardet.detect(file.read())
            encoding = result['encoding'] or 'utf-8'
            print(f"Определена кодировка: {encoding} (уверенность: {result['confidence']:.2f})")
            return encoding

    def fetch(self):
        """Читает локальный файл или скачивает страницу"""
        if self.is_local_file:
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
            print(f"Загружаю страницу: {self.source}")
            try:
                response = requests.get(self.source, headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code == 200:
                    print(f"Страница загружена, размер: {len(response.text)} символов")
                    return response.text
                print(f"Ошибка при загрузке: {response.status_code}")
            except Exception as e:
                print(f"Ошибка при запросе: {e}")
            return None

    def parse(self, html):
        """Извлекает данные из HTML"""
        soup = BeautifulSoup(html, "html.parser")
        listings = []

        for item in soup.find_all("div", class_="listing-item"):
            price_span = item.find("span", class_="price")
            address_span = item.find("span", class_="address")
            if price_span and address_span:
                listings.append({
                    "price": self.clean_text(price_span.get_text()),
                    "address": self.clean_text(address_span.get_text())
                })
        print(f"Всего найдено {len(listings)} объявлений")
        return listings

    @staticmethod
    def clean_text(text):
        """Очищает текст от лишних пробелов и символов"""
        return ' '.join(text.split()).strip() if text else ""

    def save_to_db(self, listings):
        """Сохраняет данные в SQLite"""
        if not listings:
            print("Нет данных для сохранения")
            return
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT,
                price TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for item in listings:
            cur.execute(
                "INSERT INTO listings (address, price) VALUES (?, ?)",
                (item["address"], item["price"])
            )
        conn.commit()
        conn.close()
        print(f"Сохранено {len(listings)} записей в базу {self.db_path}")

    def run(self):
        """Полный цикл: скачать - распарсить - сохранить"""
        html = self.fetch()
        if html:
            data = self.parse(html)
            if data:
                self.save_to_db(data)
            else:
                print("Не найдено данных для сохранения.")
        else:
            print("Не удалось получить HTML-контент")


if __name__ == "__main__":
    file_path = r"C:\Users\alikh\OneDrive\Desktop\Текстовый документ (2).txt"
    if os.path.exists(file_path):
        print(f"Файл найден: {file_path}")
        print(f"Размер файла: {os.path.getsize(file_path)} байт")
        fetcher = DataFetcher(file_path)
        fetcher.run()

        print("\nСодержимое базы данных:")
        conn = sqlite3.connect("data.db")
        for row in conn.execute("SELECT * FROM listings"):
            print(f"  ID: {row[0]}, Адрес: {row[1]}, Цена: {row[2]}")
        conn.close()
    else:
        print(f"Файл не найден: {file_path}")
