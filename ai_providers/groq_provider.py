# ai_providers/groq_provider.py
import json, time
from groq import Groq
from .base import AIProvider
import os
from groq._exceptions import RateLimitError 
SYSTEM_QUIZ = (
  "You are a quiz generator. Use ONLY the provided context. "
  "Language: detect the context language and write questions in that language. "
  "Respect EXACT COUNTS per type: return exactly counts.mcq MCQ, counts.tf TF, "
  "counts.short short-answer, and counts.fill cloze questions. "
  "Distribute the requested difficulties (easy|medium|hard) across the returned items; "
  "if some difficulty is missing in the request, do not use it. "
  "If the context truly lacks material, return fewer ONLY for that type (but never more). "
  "Output STRICT JSON array; each item is an object with fields: "
  "{kind('mcq'|'tf'|'short'|'fill'), difficulty('easy'|'medium'|'hard'), "
  "prompt, options(pipe-delimited for mcq/tf), correct, explanation}. "
  "No extra text."
)

SYSTEM_GRADER = (
  "You are a strict grader for short/freeform answers. "
  "Return STRICT JSON object: {\"correct\": true|false, \"reason\": \"...\"}."
)

def _json_list_or_empty(txt: str):
        try:
            data = json.loads(_sanitize_json(txt))
            return data if isinstance(data, list) else []
        except Exception:
            return []

SYSTEM_CARDS = (
        "You are a flashcard generator. Use ONLY the provided context. "
        "Return STRICT JSON list of objects: [{\"front\":\"...\",\"back\":\"...\"}, ...]. "
        "No extra text."  
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


SYSTEM_FLASHCARDS = (
        "You are a flashcard generator that ONLY uses the provided context. "
        "DETECT the language of the context and write the flashcards in that same language. "
        "Return a STRICT JSON array of objects: [{\"front\": \"...\", \"back\": \"...\"}]. "
        "Rules:\n"
        "- Max {count} cards; return fewer only if the context truly lacks distinct facts.\n"
        "- One atomic concept per card (definition, key idea, formula, step, cause→effect, term→example).\n"
        "- Avoid duplicates, trivia, or vague statements; prefer syllabus-level facts and terminology.\n"
        "- Keep it concise: each side ≤ 25 words; no markdown, no quotes, no numbering.\n"
        "- Prefer fronts as short prompts/questions; backs as precise answers.\n"
        "- If the context is long, prioritize: core definitions, theorems/rules, constraints, procedures, edge-cases.\n"
        "- DO NOT invent facts not grounded in the context.\n"
        "- Keep total output compact (token-aware). "
        )

class GroqProvider(AIProvider):
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        api_key = os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=api_key)
        self.model = model
        self.fallback_model = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")  # npr. brži/jeftiniji

    def _chat(self, system: str, user: str, retries: int = 2) -> str:
        last = ""
        model_to_use = self.model
        for i in range(retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=model_to_use,
                    messages=[{"role":"system","content":system},
                              {"role":"user","content":user}],
                    temperature=0.2,
                )
                last = resp.choices[0].message.content or ""
                if "{" in last or "[" in last:
                    break
                return last
            except RateLimitError as e:
                # 1) probaj fallback model (jednom)
                if model_to_use != self.fallback_model:
                    model_to_use = self.fallback_model
                    continue
                # 2) zadnji pokušaj – ako i dalje 429, prosledi dalje (biće uhvaćeno spolja)
                if i == retries:
                    raise
                time.sleep(1.5 * (i + 1))
            except Exception:
                if i == retries:
                    raise
                time.sleep(0.8 * (i + 1))
        return last

    


    def make_flashcards(self, context: str, n: int = 10) -> list:
        req = json.dumps({
            "count": int(max(1, n)),
            "context": (context or "")[:4000]
        })
        req = json.dumps({
            "count": int(max(1, n)),
            "context": (context or "")[:3000]  # kraći context = manji trošak, manje halucinacija
        })
        content = self._chat(SYSTEM_FLASHCARDS, req)

        try:
            data = json.loads(_sanitize_json(content))
            cards = []
            if isinstance(data, list):
                for it in data:
                    front = (it.get("front") or "").strip()
                    back  = (it.get("back") or "").strip()
                    if front and back:
                        cards.append({"front": front, "back": back})
            return cards[:n]
        except Exception:
            # fallback: ništa
            return []
    
    def summarize(self, text: str) -> dict:
        system_prompt = (
        "You are a world-class academic summarizer and study coach.\n"
        "Write EVERYTHING in the SAME language as the input text. "
        "If the input is Serbian, use Serbian (including headings). "
        "Be concise, precise, and exam-focused. "
        "If information is missing or unclear, explicitly state that rather than inventing content."
        "If the text is very short (<100 words), return it verbatim as the summary."
        "Find key concepts, terms, and names, and include them in the summary. Summary must contain at least" \
        " 15 percent of words in text that are the most important.\n"
        )
        resp = self._chat(system_prompt, text)
        return {
            "title": "Sažetak" if text.strip()[:30].isascii() is False else "Summary",
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
        
    

    def make_flashcards(self, text: str, n: int) -> list:
        req = json.dumps({"n": int(n), "context": text[:8000]})
        content = self._chat(SYSTEM_CARDS, req)
        cards = _json_list_or_empty(content)
            # normalizuj shape
        out = []
        for c in cards[:n]:
            front = (c.get("front") or "").strip()
            back  = (c.get("back") or "").strip()
            if front and back:
                out.append({"front": front, "back": back})
        return out