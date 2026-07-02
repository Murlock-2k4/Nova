import random

MORNING_PHRASES = [
    "good morning nova",
    "morning nova",
    "good morning, nova",
    "hey nova good morning",
    "nova good morning"
]

GREETING_PHRASES = [
    "hello nova",
    "hi nova",
    "hey nova",
    "hey no va",
    "nova hello",
    "nova hi"
]

GOODNIGHT_PHRASES = [
    "good night nova",
    "goodnight nova",
    "night nova",
    "nova good night"
]

THANKS_PHRASES = [
    "thank you nova",
    "thanks nova",
    "nova thank you",
    "nova thanks"
]

HOW_ARE_YOU_PHRASES = [
    "how are you nova",
    "nova how are you",
    "how's it going nova",
    "nova how's it going"
]


def handle_special_phrases(user_input: str):
    cleaned = user_input.lower().strip()

    if cleaned in MORNING_PHRASES:
        return random.choice([
            "Good morning sir.",
            "Good morning. I hope you slept well.",
            "Good morning sir. I'm ready when you are."
        ])

    if cleaned in GREETING_PHRASES:
        return random.choice([
            "Hello sir.",
            "Hi.",
            "I'm here.",
            "Yes?"
        ])

    if cleaned in GOODNIGHT_PHRASES:
        return random.choice([
            "Good night sir.",
            "Sleep well.",
            "Good night. I'll be here when you need me."
        ])

    if cleaned in THANKS_PHRASES:
        return random.choice([
            "You're welcome.",
            "Of course.",
            "Anytime."
        ])

    if cleaned in HOW_ARE_YOU_PHRASES:
        return random.choice([
            "I'm doing well.",
            "All systems are running smoothly.",
            "I'm here and ready to help."
        ])

    return None