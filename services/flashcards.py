# services/flashcards.py
import os
import services.rag as rag
from ai_providers.local_stub import LocalStub
from ai_providers.groq_provider import GroqProvider

_provider = None

def _get_provider():
    global _provider
    if _provider is not None:
        return _provider
    if os.getenv("GROQ_API_KEY"):
        try:
            _provider = GroqProvider(model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
            return _provider
        except Exception as e:
            print("Groq init failed in flashcards:", e)
    _provider = LocalStub()
    return _provider

def make_cards_from_rag(doc_id: int, full_text: str, n: int = 10) -> list:
    hint = "Generate concise Q/A flashcards for core definitions, key concepts and relationships."
    ctx = rag.build_context(doc_id, hint, top_k=5, max_chars=2000)
    if not ctx:
        ctx = (full_text or "")[:3000]

    prov = _get_provider()
    cards = prov.make_flashcards(ctx, n) or []

    if len(cards) < n:
        extra = LocalStub().make_flashcards(ctx, n - len(cards))
        cards.extend(extra)

    out = []
    for c in cards[:n]:
        f = (c.get("front") or "").strip()
        b = (c.get("back") or "").strip()
        if f and b:
            out.append({"front": f, "back": b})
    return out
