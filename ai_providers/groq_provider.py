# ai_providers/groq_provider.py
import json, time
from groq import Groq
from .base import AIProvider
import os

SYSTEM_QUIZ = (
  "You are a quiz generator. Use ONLY the provided context. "
  "If the context is insufficient, return an empty JSON array []. "
  "Questions must be grounded in the context (verbatim facts, names, terms). "
  "Return STRICT JSON list with objects: "
  "{kind('mcq'|'tf'|'short'|'fill'), difficulty('easy'|'medium'|'hard'), "
  "prompt, options(pipe-delimited for mcq/tf), correct, explanation}. "
  "No extra text."
)

SYSTEM_GRADER = (
  "You are a strict grader for short/freeform answers. "
  "Return STRICT JSON object: {\"correct\": true|false, \"reason\": \"...\"}."
)

def _sanitize_json(txt: str) -> str:
    if not txt:
        return "[]"
    t = txt.strip()
    # ukloni ```json ... ```
    if t.startswith("```"):
        t = t.strip("`")
        # posle skidanja backticka nekad ostane "json\n{...}"
        if t.lower().startswith("json"):
            t = t[4:].strip()
    # uzmi prvi JSON blok (lista ili objekat)
    start = min([i for i in [t.find("["), t.find("{")] if i != -1], default=-1)
    if start == -1:
        return "[]"
    # pokušaj da nađeš kraj skupa
    # heuristika: probaj direktan json.loads; ako puca, skraćuj do poslednjeg ']' ili '}'
    for end in range(len(t), start, -1):
        chunk = t[start:end].strip()
        try:
            json.loads(chunk)
            return chunk
        except Exception:
            continue
    return "[]"

class GroqProvider(AIProvider):
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = model

    def _chat(self, system: str, user: str, retries: int = 2) -> str:
        last = ""
        for i in range(retries + 1):
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                temperature=0.2,
            )
            last = resp.choices[0].message.content or ""
            # brzo izađi ako liči na JSON
            if ("{" in last or "[" in last):
                break
            time.sleep(0.5)
        return last

    
    def summarize(self, text: str) -> dict:
        system_prompt = (
            "You are an academic summarizer. Summarize the following text in concise, clear paragraphs. "
            "Return a short title, the summary itself, and the approximate word count."
        )
        resp = self._chat(system_prompt, text)
        return {
            "title": "Summary",
            "summary": resp.strip(),
            "word_count": len(resp.split())
        }

    def generate_quiz(self, text: str, config: dict) -> list:
        req = json.dumps({
            "counts": {
                "mcq": int(config.get("mcq", 5)),
                "tf": int(config.get("tf", 5)),
                "short": int(config.get("short", 5)),
                "fill": int(config.get("fill", 5)),
            },
            "difficulties": [d.lower() for d in config.get("difficulties", ["Easy","Medium","Hard"])],
            "context": text[:8000],
        })
        content = self._chat(SYSTEM_QUIZ, req)
        try:
            data = json.loads(_sanitize_json(content))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def grade_freeform(self, question: str, ground_truth: str, user_answer: str) -> dict:
        req = json.dumps({
            "question": question, "ground_truth": ground_truth, "user_answer": user_answer
        })
        content = self._chat(SYSTEM_GRADER, req)
        try:
            obj = json.loads(_sanitize_json(content))
            return {"correct": bool(obj.get("correct")), "reason": obj.get("reason","")}
        except Exception:
            return {"correct": False, "reason": "Parse error"}
