from speech import speak
from weather import get_weather
from calendar_tools import get_todays_events
from lights import turn_on_lights


def morning_routine():
    speak("Good morning sir.")

    lights_result = turn_on_lights()
    print("Nova:", lights_result)
    speak(lights_result)

    weather = get_weather()
    print("Nova:", weather)
    speak(weather)

    calendar = get_todays_events()
    print("Nova:", calendar)
    speak(calendar)