from tools.weather import get_weather
from tools.calendar_tools import get_todays_events
from tools.lights import turn_on_lights


def morning_routine() -> str:
    lights_result = turn_on_lights()
    weather_result = get_weather()
    calendar_result = get_todays_events()

    return (
        "Good morning sir. "
        f"{lights_result} "
        f"{weather_result} "
        f"{calendar_result}"
    )