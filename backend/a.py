import sqlite3

conn = sqlite3.connect("data.db")
cur = conn.cursor()

cur.execute("DELETE FROM listings")
conn.commit()
conn.close()

print("✅ Все записи удалены")
