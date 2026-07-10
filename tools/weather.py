import requests

from config import HOME_CITY


def geocode_city(city_name: str):
    response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={
            "name": city_name,
            "count": 1,
            "language": "en",
            "format": "json"
        },
        timeout=10
    )

    data = response.json()
    results = data.get("results", [])

    if not results:
        return None

    place = results[0]
    return {
        "name": place["name"],
        "country": place.get("country", ""),
        "latitude": place["latitude"],
        "longitude": place["longitude"],
        "timezone": place.get("timezone", "auto")
    }


def get_weather(city_name: str = HOME_CITY) -> str:
    place = geocode_city(city_name)

    if not place:
        return f"I couldn't find weather for {city_name}."

    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": 1
        },
        timeout=10
    )

    data = response.json()

    current = data.get("current", {})
    daily = data.get("daily", {})

    temp = current.get("temperature_2m")
    feels_like = current.get("apparent_temperature")
    wind = current.get("wind_speed_10m")

    high = None
    low = None
    rain = None

    if daily.get("temperature_2m_max"):
        high = daily["temperature_2m_max"][0]

    if daily.get("temperature_2m_min"):
        low = daily["temperature_2m_min"][0]

    if daily.get("precipitation_probability_max"):
        rain = daily["precipitation_probability_max"][0]

    parts = [f"Right now in {place['name']}, it's {temp} degrees Celsius"]

    if feels_like is not None:
        parts.append(f"and feels like {feels_like} degrees")

    if high is not None and low is not None:
        parts.append(f"Today's high is {high} and the low is {low}")

    if rain is not None:
        parts.append(f"with a {rain} percent chance of rain")

    if wind is not None:
        parts.append(f"Wind speed is {wind} kilometers per hour")

    return ". ".join(parts) + "."