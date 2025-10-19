# services/quizzer.py
import os, random
from ai_providers.local_stub import LocalStub
from ai_providers.groq_provider import GroqProvider
import services.rag as rag
from groq._exceptions import RateLimitError


_provider = None
_provider_name = "stub"


def _get_provider():
    global _provider, _provider_name
    if _provider is not None:
        return _provider

    if os.getenv("GROQ_API_KEY"):
        try:
            _provider = GroqProvider(model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
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

#standardizacija pitanja koja dolaze iz LLM-a
def _normalize_items(items: list) -> list:
    norm = []
    for it in items:
        kind = (it.get('kind', '') or '').lower()
        diff = (it.get('difficulty', '') or '').lower()
        prompt = (it.get('prompt', '') or '').strip()
        options = (it.get('options', '') or '').strip()
        correct = (it.get('correct', '') or '').strip()
        expl = (it.get('explanation', '') or '').strip()

        if diff not in ('easy', 'medium', 'hard'):
            diff = 'easy'

        if kind in ('mcq', 'tf'):
            if kind == 'tf':
                opts = ["A) True", "B) False"]
                c = correct.lower()
                if c in ('a', 'true', 't', 'tačno', 'tacno', '1', 'yes'):
                    correct_letter = 'A'
                elif c in ('b', 'false', 'f', 'netačno', 'netacno', '0', 'no'):
                    correct_letter = 'B'
                else:
                    correct_letter = 'A'
                options_pipe = "|".join(opts)
                norm.append({
                    'kind': 'tf', 'difficulty': diff, 'prompt': prompt,
                    'options': options_pipe, 'correct': correct_letter, 'explanation': expl
                })
                continue

            raw = options or ""
            parts = []
            if '|' in raw:
                parts = [p.strip() for p in raw.split('|') if p.strip()]
            elif ',' in raw:
                parts = [p.strip() for p in raw.split(',') if p.strip()]
            elif '\n' in raw:
                parts = [p.strip() for p in raw.splitlines() if p.strip()]
            else:
                parts = [correct] if correct else []

            clean = []
            for p in parts:
                cp = p
                if ') ' in cp[:4] and cp[1] == ')':
                    cp = cp[3:].strip()
                clean.append(cp)

            seen = set()
            uniq = []
            for p in clean:
                if p and p.lower() not in seen:
                    seen.add(p.lower())
                    uniq.append(p)

            while len(uniq) < 4:
                uniq.append(f"Distractor {len(uniq) + 1}")

            uniq = uniq[:6]
            correct_letter = None
            ctext = correct.strip().lower()
            if len(correct) == 1 and correct.upper() in "ABCDEF":
                correct_letter = correct.upper()
            else:
                for idx, p in enumerate(uniq):
                    if p.lower() == ctext and ctext != "":
                        correct_letter = "ABCDEF"[idx]
                        break
                if correct_letter is None:
                    correct_letter = 'A'

            labeled = [f"{'ABCDEF'[i]}) {p}" for i, p in enumerate(uniq)]
            options_pipe = "|".join(labeled)
            norm.append({
                'kind': 'mcq', 'difficulty': diff, 'prompt': prompt,
                'options': options_pipe, 'correct': correct_letter, 'explanation': expl
            })
        else:
            norm.append({
                'kind': 'fill' if kind == 'fill' else 'short',
                'difficulty': diff,
                'prompt': prompt,
                'options': None,
                'correct': correct,
                'explanation': expl
            })
    return norm

#osiguravanje tacnog broja pitanja po tipu, dopuna iz stub-a ako treba
def _enforce_counts(items: list, cfg: dict, context_text: str) -> list:
    want = {
        'mcq': int(cfg.get('mcq', 5)),
        'tf': int(cfg.get('tf', 5)),
        'short': int(cfg.get('short', 5)),
        'fill': int(cfg.get('fill', 5)),
    }
    buckets = {'mcq': [], 'tf': [], 'short': [], 'fill': []}
    for it in items:
        k = it.get('kind', '').lower()
        if k in buckets:
            buckets[k].append(it)

    for k in buckets:
        buckets[k] = buckets[k][:want[k]]

    stub = LocalStub()
    for k in buckets:
        need = want[k] - len(buckets[k])
        if need > 0:
            stub_cfg = {'mcq': 0, 'tf': 0, 'short': 0, 'fill': 0}
            stub_cfg[k] = need
            add = stub.generate_quiz(context_text[:2000], stub_cfg) or []
            add = _normalize_items(add)
            buckets[k].extend(add[:need])

    out = []
    for k in ('mcq', 'tf', 'short', 'fill'):
        out.extend(buckets[k])

    return out

#glavna funkcija za generisanje pitanja iz RAG konteksta
def generate_from_rag(doc_id: int, full_text: str, config: dict, user_hint: str = ""):
    prov = _get_provider()
    hint = user_hint.strip() or "Generate diverse exam questions about key facts, definitions, formulas and relationships from the document."
    context = rag.build_context(doc_id, hint, top_k=5, max_chars=2000)

    if not context:
        words = full_text.split()
        if len(words) > 600:
            start = random.randint(0, max(0, len(words) - 450))
            context = " ".join(words[start:start + 450])
        else:
            context = full_text[:4000]

    try:
        raw = prov.generate_quiz(context, config)
    except RateLimitError:
        raw = LocalStub().generate_quiz(context, config)

    items = _normalize_items(raw)
    items = _enforce_counts(items, config, context)
    provider_name = prov.__class__.__name__.replace("Provider", "").lower()
    return items, context, provider_name

#ocena odgovora korisnika od strane llm-a
def grade_freeform(question: str, ground_truth: str, user_answer: str) -> dict:
    prov = _get_provider()
    return prov.grade_freeform(question, ground_truth, user_answer)
