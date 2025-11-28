import re
class Listing:
    def __init__(self, id=None, address="", price="", coords=None, rooms=0, source=""):
        self.id = id
        self.address = address.strip()
        self.price = self._clean_price(price)
        self.coords = coords or (0.0, 0.0)
        self.rooms = int(rooms) if rooms else 0
        self.area = self._clean_area(area)
        self.source = source.strip()

    def clean_price(self, price_str): # преобразует цену в число
        if not price_str:
            return 0.0
        # убираем всё, кроме цифр и точки/запятой
        cleaned = re.sub(r'[^\d.,]', '', price_str.replace(' ', ''))
        cleaned = cleaned.replace(',', '.')
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
        
    def clean_area(self, area_input): # преобразует площадь в float
        if not area_input:
            return 0.0
        cleaned = re.sub(r'[^\d.,]', '', str(area_input).replace(' ', ''))
        cleaned = cleaned.replace(',', '.')
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def to_dict(self): # преобразует объект в словарь для JSON
        return {
            "id": self.id,
            "address": self.address,
            "price": self.price,
            "coords": self.coords,
            "rooms": self.rooms,
            "source": self.source
        }

    def validate(self): # проверяет корректность данных
        if self.price <= 0:
            return False
        if not self.address:
            return False
        return True

    def __repr__(self):
        return f"<Listing(id={self.id}, address='{self.address}', price={self.price})>"
    

    