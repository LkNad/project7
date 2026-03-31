# backend/Listing.py

from dataclasses import asdict, dataclass
from datetime import datetime
import re


def _to_float(value, default=0.0):
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        return float(value)

    cleaned = re.sub(r"[^\d.,-]", "", str(value).replace(" ", ""))
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return default


def _to_int(value, default=0):
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value

    match = re.search(r"-?\d+", str(value))
    if not match:
        return default
    try:
        return int(match.group())
    except ValueError:
        return default


@dataclass(slots=True)
class Listing:
    address: str
    price: float
    rooms: int = 0
    district: str = "Неизвестный"
    lat: float = 0.0
    lon: float = 0.0
    area: float = 0.0
    floor: int | None = None
    url: str = ""
    source: str = ""
    created_at: str | None = None
    id: int | None = None

    def __post_init__(self):
        self.address = (self.address or "").strip()
        self.price = _to_float(self.price)
        self.rooms = _to_int(self.rooms)
        self.district = (self.district or "Неизвестный").strip() or "Неизвестный"
        self.lat = _to_float(self.lat)
        self.lon = _to_float(self.lon)
        self.area = _to_float(self.area)
        self.floor = None if self.floor in (None, "") else _to_int(self.floor)
        self.url = (self.url or "").strip()
        self.source = (self.source or "").strip()
        self.created_at = self.created_at or datetime.utcnow().isoformat(timespec="seconds")

    @property
    def coords(self):
        return (self.lat, self.lon)

    def to_dict(self):
        return asdict(self)

    def to_db_tuple(self):
        return (
            self.address,
            self.price,
            self.rooms,
            self.district,
            self.lat,
            self.lon,
            self.area,
            self.floor,
            self.url,
            self.source,
            self.created_at,
        )

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"] if "id" in row.keys() else None,
            address=row["address"] if "address" in row.keys() else "",
            price=row["price"] if "price" in row.keys() else 0,
            rooms=row["rooms"] if "rooms" in row.keys() else 0,
            district=row["district"] if "district" in row.keys() else "Неизвестный",
            lat=row["lat"] if "lat" in row.keys() else 0,
            lon=row["lon"] if "lon" in row.keys() else 0,
            area=row["area"] if "area" in row.keys() else 0,
            floor=row["floor"] if "floor" in row.keys() else None,
            url=row["url"] if "url" in row.keys() else "",
            source=row["source"] if "source" in row.keys() else "",
            created_at=row["created_at"] if "created_at" in row.keys() else None,
        )

    @classmethod
    def from_raw(cls, payload, source=""):
        return cls(
            id=payload.get("id"),
            address=payload.get("address", ""),
            price=payload.get("price", 0),
            rooms=payload.get("rooms", payload.get("rooms_count", 0)),
            district=payload.get("district", "Неизвестный"),
            lat=payload.get("lat", 0),
            lon=payload.get("lon", 0),
            area=payload.get("area", payload.get("total_meters", 0)),
            floor=payload.get("floor"),
            url=payload.get("url", ""),
            source=payload.get("source", source),
            created_at=payload.get("created_at"),
        )

    def validate(self):
        return bool(self.address) and self.price >= 0

    def __repr__(self):
        return f"<Listing(id={self.id}, address='{self.address}', price={self.price})>"
