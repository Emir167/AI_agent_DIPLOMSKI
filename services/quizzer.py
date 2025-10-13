# services/quizzer.py
import os, random
from ai_providers.local_stub import LocalStub
from .chunker import random_chunk
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


def _normalize_items(items: list) -> list:
    """Sredi options u 'A)|B)|C)' formu, mapiraj correct na A/B/C..."""
    norm = []
    for it in items:
        kind = (it.get('kind','') or '').lower()
        diff = (it.get('difficulty','') or '').lower()
        prompt = (it.get('prompt','') or '').strip()
        options = (it.get('options','') or '').strip()
        correct = (it.get('correct','') or '').strip()
        expl = (it.get('explanation','') or '').strip()

        # default difficulty
        if diff not in ('easy','medium','hard'):
            diff = 'easy'

        if kind in ('mcq','tf'):
            # TF fallback
            if kind == 'tf':
                # dozvoli i varijante (True/False, T/F, Tačno/Netačno...)
                opts = ["A) True", "B) False"]
                # mapiraj correct
                c = correct.lower()
                if c in ('a','true','t','tačno','tacno','1','yes'):
                    correct_letter = 'A'
                elif c in ('b','false','f','netačno','netacno','0','no'):
                    correct_letter = 'B'
                else:
                    # ako je prazan – pretpostavi 'A'
                    correct_letter = 'A'
                options_pipe = "|".join(opts)
                norm.append({
                    'kind':'tf','difficulty':diff,'prompt':prompt,
                    'options':options_pipe,'correct':correct_letter,'explanation':expl
                })
                continue

            # MCQ normalizacija
            raw = options or ""
            parts = []

            if '|' in raw:
                parts = [p.strip() for p in raw.split('|') if p.strip()]
            elif ',' in raw:
                parts = [p.strip() for p in raw.split(',') if p.strip()]
            elif '\n' in raw:
                parts = [p.strip() for p in raw.splitlines() if p.strip()]
            else:
                # nema opcija -> napravi 3 distraktora
                parts = [correct] if correct else []

            # skini prefikse "A) ", "B) "
            clean = []
            for p in parts:
                cp = p
                if ') ' in cp[:4] and cp[1] == ')':
                    cp = cp[3:].strip()
                clean.append(cp)

            # uniq i trim
            seen = set()
            uniq = []
            for p in clean:
                if p and p.lower() not in seen:
                    seen.add(p.lower())
                    uniq.append(p)

            # ako i dalje imamo < 2 opcije, dodaj lažne distraktore
            while len(uniq) < 4:
                uniq.append(f"Distraktor {len(uniq)+1}")

            # maksimalno 6 opcija
            uniq = uniq[:6]

            # tačan kao slovo (ako je zadat kao tekst)
            correct_letter = None
            ctext = correct.strip().lower()
            # ako je već A/B/C...
            if len(correct) == 1 and correct.upper() in "ABCDEF":
                correct_letter = correct.upper()
            else:
                # pokušaj da nađeš matching tekst
                for idx, p in enumerate(uniq):
                    if p.lower() == ctext and ctext != "":
                        correct_letter = "ABCDEF"[idx]
                        break
                if correct_letter is None:
                    # ako nije našao exact, podrazumevaj da je prva opcija tačna
                    correct_letter = 'A'

            labeled = [f"{'ABCDEF'[i]}) {p}" for i,p in enumerate(uniq)]
            options_pipe = "|".join(labeled)

            norm.append({
                'kind':'mcq','difficulty':diff,'prompt':prompt,
                'options':options_pipe,'correct':correct_letter,'explanation':expl
            })
        else:
            # short / fill
            norm.append({
                'kind': 'fill' if kind == 'fill' else 'short',
                'difficulty': diff,
                'prompt': prompt,
                'options': None,
                'correct': correct,
                'explanation': expl
            })
    return norm


def _enforce_counts(items: list, cfg: dict, context_text: str) -> list:
    """Iseci/dopuni po tipu: mcq/tf/short/fill tako da dobiješ tačno koliko je traženo."""
    want = {
        'mcq': int(cfg.get('mcq', 5)),
        'tf': int(cfg.get('tf', 5)),
        'short': int(cfg.get('short', 5)),
        'fill': int(cfg.get('fill', 5)),
    }
    buckets = {'mcq':[], 'tf':[], 'short':[], 'fill':[]}
    for it in items:
        k = it.get('kind','').lower()
        if k in buckets:
            buckets[k].append(it)

    # skrati višak
    for k in buckets:
        buckets[k] = buckets[k][:want[k]]

    # dopuni manjak (fallback na LocalStub)
    stub = LocalStub()
    for k in buckets:
        need = want[k] - len(buckets[k])
        if need > 0:
            # traži da stub generiše baš taj tip
            stub_cfg = {'mcq':0, 'tf':0, 'short':0, 'fill':0}
            stub_cfg[k] = need
            add = stub.generate_quiz(context_text[:2000], stub_cfg) or []
            add = _normalize_items(add)
            buckets[k].extend(add[:need])

    # sklopi u zadatom redosledu (možeš i pomešati)
    out = []
    for k in ('mcq','tf','short','fill'):
        out.extend(buckets[k])

    return out


def generate_from_rag(doc_id: int, full_text: str, config: dict, user_hint: str = ""):
    prov = _get_provider()
    hint = user_hint.strip() or "Generate diverse exam questions about key facts, definitions, formulas and relationships from the document."
    context = rag.build_context(doc_id, hint, top_k=5, max_chars=2000)
    if not context:
        words = full_text.split()
        if len(words) > 600:
            start = random.randint(0, max(0, len(words)-450))
            context = " ".join(words[start:start+450])
        else:
            context = full_text[:4000]

    raw = prov.generate_quiz(context, config) or []
    items = _normalize_items(raw)
    items = _enforce_counts(items, config, context)
    provider_name = prov.__class__.__name__.replace("Provider","").lower()
    return items, context, provider_name



def _get_provider():
    global _provider
    if _provider:
        return _provider
    _provider = GroqProvider() if os.getenv("GROQ_API_KEY") else LocalStub()
    return _provider

def generate_from_random_chunk(text: str, config: dict, target_words: int = 350):
    prov = _get_provider()
    # stara random chunk logika ako hoćeš fallback...
    try:
        items = prov.generate_quiz(context, config)
    except RateLimitError:
        items = LocalStub().generate_quiz(context, config)
    return items, text[: target_words*6], prov.__class__.__name__.lower()

def generate_from_rag(doc_id: int, full_text: str, config: dict, user_hint: str = ""):
    prov = _get_provider()
    context = rag.build_context(doc_id, user_hint, top_k=6, max_chars=5000)

    try:
        items = prov.generate_quiz(context, config)
    except RateLimitError:
        items = LocalStub().generate_quiz(context, config)
    provider_name = prov.__class__.__name__.replace("Provider","").lower()
    return items, context, provider_name

def grade_freeform(question: str, ground_truth: str, user_answer: str) -> dict:
    prov = _get_provider()
    return prov.grade_freeform(question, ground_truth, user_answer)
