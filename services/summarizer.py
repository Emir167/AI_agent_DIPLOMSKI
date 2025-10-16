# services/summarizer.py
import json, re
from ai_providers.groq_provider import GroqProvider
import services.rag as rag
from groq._exceptions import RateLimitError

_provider = GroqProvider()

# --- MAP i REDUCE sistem poruke (kratke, robustne) ---
SYSTEM_MAP = (
    "Sažmi sledeći pasus/odeljak u 3–6 jasnih rečenica, koristi jezik izvornog teksta. "
    "Zadrži ključne pojmove, definicije, relacije i primere. Ne uvodi nove informacije."
)

SYSTEM_REDUCE = (
    "Spajanje delimičnih sažetaka. "
    "Napravi koherentan sažetak celog teksta u 1–3 pasusa (8–14 rečenica ukupno), "
    "sa jasnim tokovima: (1) tema/opseg, (2) glavne ideje/definicije/relacije, (3) zaključak/upotreba. "
    "Vrati JSON: {\"title\": \"...\", \"summary\": \"...\"}. Jezik isti kao ulaz."
)

def _chat(system: str, user: str) -> str:
    # koristi interni chat iz provajdera (isti kao u groq_provideru)
    return _provider._chat(system, user)


def _chat(system, user):
    return _provider._chat(system, user)

def _stub_map(chunks):
    out = []
    for ch in chunks:
        # uzmi 1–2 najinformativnije rečenice (prosta heuristika)
        sents = re.split(r'(?<=[.!?])\s+', ch.strip())
        pick = " ".join(sents[:2]).strip()
        out.append(f"- {pick}")
    return "\n".join(out)

def _stub_reduce(bullets):
    # skrati na ~160 reči
    words = bullets.split()
    if len(words) > 180:
        words = words[:180]
    return " ".join(words)

def summarize_via_rag(doc_id: int, full_text: str, query: str = "", max_chunks: int = 6, top_k: int = 6):
    # manji top_k da trošimo manje tokena
    ctx_list = rag.search(doc_id, query or "najvažnije teme, definicije, relacije", top_k=top_k)
    chunks = rag.pick_chunks(ctx_list, max_chunks=max_chunks, max_chars=900)  # *kraći* chunkovi

    # MAP faza
    try:
        map_bullets = []
        for ch in chunks:
            part = _chat(SYSTEM_MAP, ch) or ""
            map_bullets.append(part.strip())
        mapped = "\n".join(map_bullets) if map_bullets else _stub_map(chunks)
    except RateLimitError:
        mapped = _stub_map(chunks)

    # REDUCE faza
    try:
        final = _chat(SYSTEM_REDUCE, mapped) or _stub_reduce(mapped)
    except RateLimitError:
        final = _stub_reduce(mapped)

    final = final.strip()
    return {
        "title": "Sažetak",
        "summary": final,
        "word_count": len(final.split())
    }

def summarize(text: str) -> dict:
    """Direktan sažetak (bez RAG-a) — fallback/legacy."""
    resp = _provider.summarize(text)
    return resp

def summarize_via_rag(doc_id: int, full_text: str, *, query: str = "",
                      max_chunks: int = 8, top_k: int = 10) -> dict:
    """
    Map-Reduce summarization preko RAG-a.
    1) ensure_index -> retrieve najrelevantnije delove (po query ili generički),
    2) MAP: parcijalni sažeci po chunku,
    3) REDUCE: spajanje u finalni, uz naslov.
    """
    # 1) indeks
    rag.ensure_index(doc_id, full_text)

    # 2) retrieve
    q = (query or "Sažmi glavne ideje, definicije, relacije i primere iz dokumenta.").strip()
    hits = rag.retrieve(doc_id, q, top_k=top_k)
    if not hits:
        return summarize(full_text)

    chunks = [h["text"] for h in hits[:max_chunks]]

    partials = []
    for ch in chunks:
        part = _chat(SYSTEM_MAP, ch) or ""
        partials.append(part.strip())

    reduce_input = json.dumps({"partials": partials}, ensure_ascii=False)
    reduced_raw = _chat(SYSTEM_REDUCE, reduce_input) or ""
    try:
        t = reduced_raw.strip()
        start = t.find("{")
        end = t.rfind("}")
        obj = {}
        if start != -1 and end != -1:
            obj = json.loads(t[start:end+1])
        title = obj.get("title") or "Sažetak"
        summary = (obj.get("summary") or reduced_raw).strip()
    except Exception:
        title = "Sažetak"
        summary = reduced_raw.strip()

    wc = len(summary.split())
    return {"title": title, "summary": summary, "word_count": wc}
