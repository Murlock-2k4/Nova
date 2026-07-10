import requests
from config import OLLAMA_URL, OLLAMA_MODEL
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are Nova, a smart home voice assistant.
Reply briefly, clearly, and naturally.
Keep most answers to 1 or 2 short sentences unless the user asks for more.
Sound calm, helpful, and slightly polished.
"""

def ask_nova(user_text: str) -> str:
    logger.info("Sending request to Ollama")

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": f"{SYSTEM_PROMPT}\n\nUser: {user_text}",
                "stream": False,
            },
            timeout=60,
        )

        response.raise_for_status()

        reply = response.json().get("response", "").strip()

        if not reply:
            logger.warning("Ollama returned an empty response")
            return "I didn't receive a response from my language model."

        return reply

    except requests.ConnectionError:
        logger.exception("Could not connect to Ollama")
        return "I can't reach Ollama. Please check whether it is running."

    except requests.Timeout:
        logger.exception("Ollama request timed out")
        return "My language model took too long to respond."

    except requests.RequestException:
        logger.exception("Ollama request failed")
        return "Something went wrong while contacting my language model."

    except (KeyError, ValueError, TypeError):
        logger.exception("Invalid response received from Ollama")
        return "I received an invalid response from my language model."