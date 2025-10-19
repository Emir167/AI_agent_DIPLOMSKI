# services/coach.py
from ai_providers.groq_provider import GroqProvider
import services.rag as rag
import json

_provider = GroqProvider()

SYSTEM_COACH = (
  "You are a study coach. Answer concisely using ONLY the given context and plan info. "
  "If you don't find an answer in the context, say you cannot find the answer based on the provided information and" \
  "search on the web or other sources. Than answer and say that you found the answer elsewhere." \
  "Answer in the language of the question."
)

def answer(q: str, full_text: str, plan_info: str, doc_id: int = None):
    if doc_id is not None:
        ctx = rag.build_context(doc_id, q, top_k=6, max_chars=15000)
    else:
        ctx = full_text[:4000]
    user = json.dumps({"question": q, "plan": plan_info, "context": ctx}, ensure_ascii=False)
    resp = _provider._chat(SYSTEM_COACH, user)
    return resp.strip()