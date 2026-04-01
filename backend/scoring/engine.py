from __future__ import annotations

from collections import defaultdict
from statistics import median


def _clamp(value, minimum=0.0, maximum=100.0):
    return max(minimum, min(maximum, round(value, 2)))


def _average(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 2) if values else 0.0


def _percentile_position(value, series):
    valid = sorted(item for item in series if item is not None)
    if not valid:
        return 0.5
    lower = sum(1 for item in valid if item <= value)
    return lower / len(valid)


def _quality_band(score):
    if score >= 80:
        return "Сильный"
    if score >= 65:
        return "Сбалансированный"
    if score >= 50:
        return "Компромиссный"
    return "Рискованный"


def _district_profile(family_score, investment_score, transport_score):
    ranking = sorted(
        [
            (family_score, "family-friendly"),
            (investment_score, "investment-friendly"),
            (transport_score, "commute-friendly"),
        ],
        reverse=True,
    )
    return ranking[0][1]


def build_market_context(listings, filters=None):
    filters = filters or {}
    by_district = defaultdict(list)
    prices = []
    price_per_m2_values = []
    metro_times = []
    areas = []

    for listing in listings:
        by_district[listing["district"]].append(listing)
        if listing.get("price"):
            prices.append(listing["price"])
        if listing.get("price_per_m2"):
            price_per_m2_values.append(listing["price_per_m2"])
        if listing.get("metro_time_min") is not None:
            metro_times.append(listing["metro_time_min"])
        if listing.get("area"):
            areas.append(listing["area"])

    return {
        "filters": filters,
        "all_prices": prices,
        "all_price_per_m2": price_per_m2_values,
        "all_metro_times": metro_times,
        "all_areas": areas,
        "districts": by_district,
        "global_median_price": median(prices) if prices else 0,
        "global_median_ppm2": median(price_per_m2_values) if price_per_m2_values else 0,
        "global_median_metro": median(metro_times) if metro_times else 15,
        "global_median_area": median(areas) if areas else 50,
    }


def _budget_fit_score(listing, filters):
    price_min, price_max = filters.get("price_range", [0, 0])
    if not price_max:
        return 70.0
    if price_min <= listing["price"] <= price_max:
        distance = abs(((price_min + price_max) / 2) - listing["price"])
        span = max(price_max - price_min, 1)
        return _clamp(100 - (distance / span) * 60, 55, 100)
    overflow = min(abs(listing["price"] - price_max), abs(listing["price"] - price_min))
    return _clamp(60 - (overflow / max(price_max, 1)) * 100, 0, 60)


def _transport_score(listing, context):
    metro_time = listing.get("metro_time_min")
    if metro_time is None:
        metro_time = context["global_median_metro"]
    score = 100 - metro_time * 4
    if listing.get("lat") and listing.get("lon"):
        score += 5
    return _clamp(score)


def _infra_score(listing):
    score = 45
    district_name = (listing.get("district") or "").lower()
    if any(token in district_name for token in ["хамов", "твер", "арбат", "пресн", "яким"]):
        score += 25
    if any(token in district_name for token in ["алексе", "сокол", "измай", "фил"]):
        score += 15
    if listing.get("rooms", 0) >= 3:
        score += 10
    if listing.get("area", 0) >= 70:
        score += 10
    if listing.get("metro_station"):
        score += 5
    return _clamp(score)


def _family_score(listing, transport_score, infra_score):
    score = infra_score * 0.55 + transport_score * 0.2
    if listing.get("rooms", 0) >= 3:
        score += 15
    if listing.get("area", 0) >= 65:
        score += 10
    if (listing.get("floor") or 0) > 0 and (listing.get("total_floors") or 0) > 0:
        score += 5
    return _clamp(score)


def _investment_score(listing, context, district_median_ppm2):
    ppm2 = listing.get("price_per_m2") or 0
    local_median = district_median_ppm2 or context["global_median_ppm2"] or ppm2
    if local_median <= 0:
        value_component = 50
    else:
        value_component = 50 + ((local_median - ppm2) / local_median) * 50
    liquidity = 10 if listing.get("rooms") in {1, 2} else 0
    return _clamp(value_component + liquidity + 20)


def _value_score(listing, district_listings, context):
    ppm2 = listing.get("price_per_m2") or 0
    district_ppm2 = [item.get("price_per_m2", 0) for item in district_listings if item.get("price_per_m2")]
    benchmark = median(district_ppm2) if district_ppm2 else context["global_median_ppm2"]
    if benchmark <= 0 or ppm2 <= 0:
        return 55.0
    delta = (benchmark - ppm2) / benchmark
    return _clamp(70 + delta * 120, 15, 100)


def _fit_score(listing, filters):
    score = _budget_fit_score(listing, filters)
    desired_rooms = filters.get("rooms")
    if desired_rooms is not None:
        if desired_rooms == "4+":
            score += 10 if listing.get("rooms", 0) >= 4 else -10
        else:
            score += 12 if listing.get("rooms") == desired_rooms else -6
    district = filters.get("district")
    if district:
        score += 8 if listing.get("district") == district else -8
    max_metro_time = filters.get("max_metro_time")
    if max_metro_time:
        metro_time = listing.get("metro_time_min") or max_metro_time + 5
        score += 10 if metro_time <= max_metro_time else -12
    return _clamp(score)


def build_districts(enriched_listings, filters=None):
    filters = filters or {}
    grouped = defaultdict(list)
    for listing in enriched_listings:
        grouped[listing["district"]].append(listing)

    budget_max = filters.get("price_range", [0, 0])[1]
    districts = []
    for district, items in grouped.items():
        avg_price = _average([item["price"] for item in items])
        avg_ppm2 = _average([item["price_per_m2"] for item in items])
        avg_area = _average([item["area"] for item in items])
        avg_rooms = _average([item["rooms"] for item in items])
        transport_score = _average([item["scores"]["transport_score"] for item in items])
        infra_score = _average([item["scores"]["infra_score"] for item in items])
        family_score = _average([item["scores"]["family_score"] for item in items])
        investment_score = _average([item["scores"]["investment_score"] for item in items])
        object_score = _average([item["scores"]["object_score"] for item in items])
        budget_fit_score = _clamp(100 - (avg_price / budget_max) * 100, 20, 95) if budget_max else 70
        district_score = _clamp(
            object_score * 0.35
            + transport_score * 0.2
            + infra_score * 0.2
            + family_score * 0.15
            + investment_score * 0.1
        )
        highlights = []
        if transport_score >= 75:
            highlights.append("сильная транспортная доступность")
        if family_score >= 75:
            highlights.append("подходит для семейного сценария")
        if investment_score >= 75:
            highlights.append("интересен для инвестиционного сценария")
        if budget_fit_score >= 70:
            highlights.append("относительно доступен в рамках текущего бюджета")
        if not highlights:
            highlights.append("требует компромисса между ценой и качеством")

        districts.append(
            {
                "district": district,
                "listing_count": len(items),
                "avg_price": avg_price,
                "avg_price_per_m2": avg_ppm2,
                "avg_area": avg_area,
                "avg_rooms": avg_rooms,
                "transport_score": transport_score,
                "infra_score": infra_score,
                "family_score": family_score,
                "investment_score": investment_score,
                "district_score": district_score,
                "budget_fit_score": budget_fit_score,
                "quality_band": _quality_band(district_score),
                "profile_label": _district_profile(family_score, investment_score, transport_score),
                "highlights": highlights,
            }
        )

    return sorted(districts, key=lambda item: (-item["district_score"], -item["listing_count"], item["district"]))


def _recommendation_reasons(listing, district_entry, district_listings, filters, context):
    reasons = []
    district_prices = [item["price"] for item in district_listings if item.get("price")]
    district_ppm2 = [item["price_per_m2"] for item in district_listings if item.get("price_per_m2")]
    district_median_price = median(district_prices) if district_prices else listing["price"]
    district_median_ppm2 = median(district_ppm2) if district_ppm2 else listing["price_per_m2"]

    if listing["price"] and district_median_price and listing["price"] < district_median_price:
        discount = round((district_median_price - listing["price"]) / district_median_price * 100, 1)
        reasons.append(f"ниже медианной цены района на {discount}%")

    if listing.get("price_per_m2") and district_median_ppm2 and listing["price_per_m2"] < district_median_ppm2:
        discount = round((district_median_ppm2 - listing["price_per_m2"]) / district_median_ppm2 * 100, 1)
        reasons.append(f"цена за м² лучше локальной выборки на {discount}%")

    metro_percentile = _percentile_position(
        listing.get("metro_time_min") or context["global_median_metro"],
        [item.get("metro_time_min") for item in district_listings if item.get("metro_time_min") is not None],
    )
    if metro_percentile <= 0.4:
        reasons.append("ближе к метро, чем значимая часть сопоставимых объектов")

    if district_entry["family_score"] >= 75:
        reasons.append("район имеет высокий family score")
    if district_entry["transport_score"] >= 75:
        reasons.append("район имеет высокий transport score")
    if filters.get("price_range") and filters["price_range"][0] <= listing["price"] <= filters["price_range"][1]:
        reasons.append("объект укладывается в заданный бюджет")
    if filters.get("max_metro_time") and (listing.get("metro_time_min") or 999) <= filters["max_metro_time"]:
        reasons.append("соответствует ограничению по commute time")
    if listing["scores"]["object_score"] >= 75:
        reasons.append("даёт сильный баланс цены, локации и инфраструктуры")

    return reasons[:5] or ["рекомендован как сбалансированный вариант на текущих данных"]


def enrich_listings(listings, filters=None):
    filters = filters or {}
    context = build_market_context(listings, filters)
    enriched = []
    district_index = {}

    for district_name, items in context["districts"].items():
        district_index[district_name] = {
            "median_ppm2": median([item.get("price_per_m2", 0) for item in items if item.get("price_per_m2")]) if items else 0,
            "items": items,
        }

    for listing in listings:
        district_entry = district_index[listing["district"]]
        value_score = _value_score(listing, district_entry["items"], context)
        transport_score = _transport_score(listing, context)
        infra_score = _infra_score(listing)
        fit_score = _fit_score(listing, filters)
        family_score = _family_score(listing, transport_score, infra_score)
        investment_score = _investment_score(listing, context, district_entry["median_ppm2"])
        metro_time = listing.get("metro_time_min")
        liquidity_score = _clamp(
            55
            + (10 if listing.get("rooms") in {1, 2} else 0)
            + (10 if (metro_time if metro_time is not None else 99) <= 12 else 0)
        )
        quality_signal = _clamp(
            35
            + (15 if listing.get("description") else 0)
            + (15 if listing.get("image_url") else 0)
            + (10 if listing.get("title") else 0)
            + (10 if listing.get("metro_station") else 0)
            + (15 if listing.get("lat") and listing.get("lon") else 0)
        )
        district_bonus = _clamp((transport_score * 0.4) + (infra_score * 0.6))
        object_score = _clamp(
            value_score * 0.30
            + transport_score * 0.25
            + infra_score * 0.20
            + fit_score * 0.15
            + district_bonus * 0.10
        )

        enriched.append(
            {
                **listing,
                "scores": {
                    "object_score": object_score,
                    "value_score": value_score,
                    "transport_score": transport_score,
                    "infra_score": infra_score,
                    "fit_score": fit_score,
                    "family_score": family_score,
                    "investment_score": investment_score,
                    "liquidity_score": liquidity_score,
                    "quality_signal": quality_signal,
                    "district_bonus": district_bonus,
                },
            }
        )

    districts = build_districts(enriched, filters)
    districts_by_name = {item["district"]: item for item in districts}
    for listing in enriched:
        district_entry = districts_by_name[listing["district"]]
        listing["district_score"] = district_entry["district_score"]
        listing["recommendation_reasons"] = _recommendation_reasons(
            listing,
            district_entry,
            district_index[listing["district"]]["items"],
            filters,
            context,
        )
        listing["profile_fit"] = _district_profile(
            listing["scores"]["family_score"],
            listing["scores"]["investment_score"],
            listing["scores"]["transport_score"],
        )

    recommendations = sorted(
        enriched,
        key=lambda item: (
            -item["scores"]["object_score"],
            -item["district_score"],
            item["price"],
        ),
    )[:5]
    return enriched, districts, recommendations
