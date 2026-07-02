import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3"

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
            "model": MODEL_NAME,
            "prompt": f"{SYSTEM_PROMPT}\n\nUser: {user_text}",
            "stream": False
        }
    )

    response.raise_for_status()
    return response.json()["response"].strip()