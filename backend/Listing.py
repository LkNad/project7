from __future__ import annotations

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


def _clean_text(value, default=""):
    normalized = " ".join(str(value or "").split()).strip()
    return normalized or default


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
    title: str = ""
    price_per_m2: float = 0.0
    image_url: str = ""
    description: str = ""
    deal_type: str = "sale"
    building_type: str = "Не указано"
    total_floors: int | None = None
    metro_station: str = ""
    metro_time_min: int | None = None
    geocode_status: str = "pending"
    geocode_source: str = ""
    geocode_confidence: float = 0.0
    map_point: str = ""

    def __post_init__(self):
        self.address = _clean_text(self.address)
        self.price = _to_float(self.price)
        self.rooms = _to_int(self.rooms)
        self.district = _clean_text(self.district, "Неизвестный")
        self.lat = _to_float(self.lat)
        self.lon = _to_float(self.lon)
        self.area = _to_float(self.area)
        self.floor = None if self.floor in (None, "") else _to_int(self.floor)
        self.url = _clean_text(self.url)
        self.source = _clean_text(self.source)
        self.title = _clean_text(self.title, self.address)
        self.image_url = _clean_text(self.image_url)
        self.description = _clean_text(self.description)
        self.deal_type = _clean_text(self.deal_type, "sale").lower()
        self.building_type = _clean_text(self.building_type, "Не указано")
        self.total_floors = None if self.total_floors in (None, "") else _to_int(self.total_floors)
        self.metro_station = _clean_text(self.metro_station)
        self.metro_time_min = None if self.metro_time_min in (None, "") else _to_int(self.metro_time_min)
        self.geocode_status = _clean_text(self.geocode_status, "pending").lower()
        self.geocode_source = _clean_text(self.geocode_source)
        self.geocode_confidence = _to_float(self.geocode_confidence)
        self.map_point = _clean_text(self.map_point)
        self.created_at = self.created_at or datetime.utcnow().isoformat(timespec="seconds")

        if not self.map_point and self.lat and self.lon:
            self.map_point = f"{self.lat:.6f},{self.lon:.6f}"

        if self.price_per_m2 in (None, "", 0, 0.0):
            self.price_per_m2 = round(self.price / self.area, 2) if self.area > 0 else 0.0
        else:
            self.price_per_m2 = _to_float(self.price_per_m2)

    @property
    def coords(self):
        return (self.lat, self.lon)

    def to_dict(self):
        payload = asdict(self)
        payload["source_url"] = self.url
        payload["latitude"] = self.lat
        payload["longitude"] = self.lon
        payload["map_point"] = self.map_point
        return payload

    def to_db_tuple(self):
        return (
            self.title,
            self.address,
            self.price,
            self.rooms,
            self.district,
            self.lat,
            self.lon,
            self.area,
            self.floor,
            self.total_floors,
            self.price_per_m2,
            self.url,
            self.image_url,
            self.description,
            self.deal_type,
            self.building_type,
            self.metro_station,
            self.metro_time_min,
            self.geocode_status,
            self.geocode_source,
            self.geocode_confidence,
            self.map_point,
            self.source,
            self.created_at,
        )

    @classmethod
    def from_row(cls, row):
        keys = set(row.keys())
        return cls(
            id=row["id"] if "id" in keys else None,
            title=row["title"] if "title" in keys else "",
            address=row["address"] if "address" in keys else "",
            price=row["price"] if "price" in keys else 0,
            rooms=row["rooms"] if "rooms" in keys else 0,
            district=row["district"] if "district" in keys else "Неизвестный",
            lat=row["lat"] if "lat" in keys else 0,
            lon=row["lon"] if "lon" in keys else 0,
            area=row["area"] if "area" in keys else 0,
            floor=row["floor"] if "floor" in keys else None,
            total_floors=row["total_floors"] if "total_floors" in keys else None,
            price_per_m2=row["price_per_m2"] if "price_per_m2" in keys else 0,
            url=row["url"] if "url" in keys else "",
            image_url=row["image_url"] if "image_url" in keys else "",
            description=row["description"] if "description" in keys else "",
            deal_type=row["deal_type"] if "deal_type" in keys else "sale",
            building_type=row["building_type"] if "building_type" in keys else "Не указано",
            metro_station=row["metro_station"] if "metro_station" in keys else "",
            metro_time_min=row["metro_time_min"] if "metro_time_min" in keys else None,
            geocode_status=row["geocode_status"] if "geocode_status" in keys else "pending",
            geocode_source=row["geocode_source"] if "geocode_source" in keys else "",
            geocode_confidence=row["geocode_confidence"] if "geocode_confidence" in keys else 0,
            map_point=row["map_point"] if "map_point" in keys else "",
            source=row["source"] if "source" in keys else "",
            created_at=row["created_at"] if "created_at" in keys else None,
        )

    @classmethod
    def from_raw(cls, payload, source=""):
        return cls(
            id=payload.get("id"),
            title=payload.get("title", payload.get("address", "")),
            address=payload.get("address", ""),
            price=payload.get("price", 0),
            rooms=payload.get("rooms", payload.get("rooms_count", 0)),
            district=payload.get("district", "Неизвестный"),
            lat=payload.get("lat", payload.get("latitude", 0)),
            lon=payload.get("lon", payload.get("longitude", 0)),
            area=payload.get("area", payload.get("total_meters", 0)),
            floor=payload.get("floor"),
            total_floors=payload.get("total_floors"),
            price_per_m2=payload.get("price_per_m2", 0),
            url=payload.get("url", payload.get("source_url", "")),
            image_url=payload.get("image_url", ""),
            description=payload.get("description", ""),
            deal_type=payload.get("deal_type", "sale"),
            building_type=payload.get("building_type", "Не указано"),
            metro_station=payload.get("metro_station", ""),
            metro_time_min=payload.get("metro_time_min"),
            geocode_status=payload.get("geocode_status", "pending"),
            geocode_source=payload.get("geocode_source", ""),
            geocode_confidence=payload.get("geocode_confidence", 0),
            map_point=payload.get("map_point", ""),
            source=payload.get("source", source),
            created_at=payload.get("created_at"),
        )

    def validate(self):
        return bool(self.address) and self.price >= 0

    def __repr__(self):
        return f"<Listing(id={self.id}, address='{self.address}', price={self.price})>"
