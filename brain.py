import requests
from config import OLLAMA_URL, OLLAMA_MODEL

SYSTEM_PROMPT = """
You are Nova, a smart home voice assistant.
Reply briefly, clearly, and naturally.
Keep most answers to 1 or 2 short sentences unless the user asks for more.
Sound calm, helpful, and slightly polished.
"""

def ask_nova(user_text: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": f"{SYSTEM_PROMPT}\n\nUser: {user_text}",
            "stream": False
        }
    )

    response.raise_for_status()
    return response.json()["response"].strip()