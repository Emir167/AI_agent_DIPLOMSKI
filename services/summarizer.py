# services/summarizer.py
import json
from ai_providers.groq_provider import GroqProvider, SYSTEM_SUMMARIZER
import services.rag as rag

_provider = GroqProvider()

def _chat(system: str, user: str) -> str:
    return _provider._chat(system, user)

def summarize(text: str) -> dict:
    resp = _provider.summarize(text)
    return resp

def summarize_via_rag(doc_id: int, full_text: str, *, query: str = "",
                      max_chunks: int = 8, top_k: int = 10) -> dict:
    rag.ensure_index(doc_id, full_text)
    q = (query or "Sažmi glavne ideje, definicije, relacije i primere iz dokumenta.").strip()
    hits = rag.retrieve(doc_id, q, top_k=top_k)
    if not hits:
        return summarize(full_text)

    chunks = [h["text"] for h in hits[:max_chunks]]
    combined = "\n\n".join(chunks)
    reduced_raw = _chat(SYSTEM_SUMMARIZER, combined) or ""
    summary = reduced_raw.strip()
    wc = len(summary.split())
    return {"title": "Sažetak", "summary": summary, "word_count": wc}
