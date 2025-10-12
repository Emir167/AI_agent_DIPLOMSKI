# services/coach.py
import os, re, json
from groq import Groq

def _chunks(text, size=800):
    words = text.split()
    for i in range(0, len(words), size):
        yield " ".join(words[i:i+size])

def answer(question: str, doc_text: str, plan_info: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=api_key)
    context = "\n\n".join(list(_chunks(doc_text, 250))[:3])  # do ~750 reči
    system = (
      "You are a helpful study coach. Use only the provided context and study plan. "
      "Answer concisely and practically. If unknown, say you don't know."
    )
    usr = f"Context:\n{context}\n\nPlan:\n{plan_info}\n\nQuestion:\n{question}"
    resp = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        messages=[{"role":"system","content":system},{"role":"user","content":usr}],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()