import json
import requests
from .base import AIProvider

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"  # default

SYSTEM_QUIZ = (
  "You are a quiz generator. From the given context, create questions with answers.\n"
  "Return STRICT JSON list of objects with keys: kind, difficulty, prompt, options (pipe-delimited for mcq/tf), correct, explanation.\n"
  "Kinds: mcq|tf|short|fill. Difficulties: easy|medium|hard.\n"
  "Do not include any text before or after JSON."
)

SYSTEM_GRADER = (
  "You are a strict grader for short/freeform answers. Decide if user's answer is correct enough.\n"
  "Return STRICT JSON object: {\"correct\": true|false, \"reason\": \"...\"}.\n"
  "Be tolerant to synonyms and minor paraphrasing; focus on factual equivalence."
)

def _chat(model: str, system: str, user: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0.2}
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data.get("message", {}).get("content", "")

class OllamaProvider(AIProvider):
    def __init__(self, model: str = "llama3"):
        self.model = model

    def summarize(self, text: str) -> dict:
        content = _chat(
            self.model,
            "You summarize text in 6 sentences max. Return plain text.",
            text[:6000]
        )
        words = len(content.split())
        return {"title": "Content Summary", "summary": content, "word_count": words}

    def generate_quiz(self, text: str, config: dict) -> list:
        n_mcq  = int(config.get('mcq', 5))
        n_tf   = int(config.get('tf', 5))
        n_short= int(config.get('short', 5))
        n_fill = int(config.get('fill', 5))
        diffs  = config.get('difficulties', ['Easy','Medium','Hard'])
        req = json.dumps({
            "counts": {"mcq": n_mcq, "tf": n_tf, "short": n_short, "fill": n_fill},
            "difficulties": [d.lower() for d in diffs],
            "context": text[:8000]
        })
        content = _chat(self.model, SYSTEM_QUIZ, req)
        try:
            items = json.loads(content)
            assert isinstance(items, list)
            return items
        except Exception:
            return []

    def grade_freeform(self, question: str, ground_truth: str, user_answer: str) -> dict:
        req = json.dumps({
            "question": question,
            "ground_truth": ground_truth,
            "user_answer": user_answer
        })
        content = _chat(self.model, SYSTEM_GRADER, req)
        try:
            obj = json.loads(content)
            return {"correct": bool(obj.get("correct")), "reason": obj.get("reason","")}
        except Exception:
            return {"correct": False, "reason": "Model response parse error"}
