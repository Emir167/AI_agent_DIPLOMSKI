# services/quizzer.py
import os
from ai_providers.local_stub import LocalStub
from .chunker import random_chunk

_provider = None
_provider_name = "stub"

def _get_provider():
    global _provider, _provider_name
    if _provider is not None:
        return _provider

    if os.getenv("GROQ_API_KEY"):
        try:
            from ai_providers.groq_provider import GroqProvider
            _provider = GroqProvider(model=os.getenv("GROQ_MODEL", "llama3-8b-8192"))
            _provider_name = "groq"
            return _provider
        except Exception as e:
            print("Groq init failed:", e)

    _provider = LocalStub()
    _provider_name = "stub"
    return _provider

def get_provider_name():
    _get_provider()
    return _provider_name

def generate_from_random_chunk(full_text: str, config: dict, target_words: int = 300):
    chunk = random_chunk(full_text, target_words=target_words)
    prov = _get_provider()
    items = prov.generate_quiz(chunk, config)
    used = get_provider_name()
    if not items:
        items = LocalStub().generate_quiz(chunk, config)
        used = "stub(fallback)"
    return items, chunk, used

def grade_freeform(question: str, ground_truth: str, user_answer: str):
    return _get_provider().grade_freeform(question, ground_truth, user_answer)
