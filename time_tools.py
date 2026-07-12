from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

from config import TIMEZONE


def find_city_timezone(city_name: str) -> dict[str, str] | None:
    response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={
            "name": city_name,
            "count": 1,
            "language": "en",
            "format": "json",
        },
        timeout=10,
    )
    response.raise_for_status()

    results = response.json().get("results", [])

    if not results:
        return None

    place = results[0]
    timezone_name = place.get("timezone")

    if not timezone_name:
        return None

    return {
        "name": place.get("name", city_name),
        "country": place.get("country", ""),
        "timezone": timezone_name,
    }


def get_current_time(city_name: str | None = None) -> str:
    if not city_name:
        now = datetime.now(ZoneInfo(TIMEZONE))
        time_text = now.strftime("%I:%M %p").lstrip("0")
        return f"It is {time_text}."

    place = find_city_timezone(city_name.strip())

    if not place:
        return f"I couldn't find a timezone for {city_name}."

    try:
        now = datetime.now(ZoneInfo(place["timezone"]))
    except ZoneInfoNotFoundError:
        return f"I couldn't load the timezone for {place['name']}."

    time_text = now.strftime("%I:%M %p").lstrip("0")
    location = place["name"]

    if place["country"]:
        location = f"{location}, {place['country']}"

    return f"It is {time_text} in {location}."
