# services/summarizer.py
import os
from dotenv import load_dotenv

# fallback učitavanje .env ako app nije (bezbedno je više puta pozvati)
load_dotenv()

_provider = None

def _get_provider():
    global _provider
    if _provider is None:
        from ai_providers.groq_provider import GroqProvider
        _provider = GroqProvider(model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
    return _provider

def summarize(text: str):
    """Return dict with keys: title, summary, word_count."""
    return _get_provider().summarize(text)
