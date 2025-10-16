# services/rag.py
import os, json, math, re
import numpy as np
from typing import List, Dict
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity



_embedder = None

def _get_model():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embedder

def set_store_dir(root_dir: str):
    """Pozovi iz app.py da RAG radi u runtime folderu (privremeno)."""
    global RAG_ROOT
    RAG_ROOT = os.path.join(root_dir, "rag_store")
    os.makedirs(RAG_ROOT, exist_ok=True)

def _doc_dir(doc_id: int) -> str:
    assert RAG_ROOT, "Call set_store_dir(RUNTIME_DIR) first"
    d = os.path.join(RAG_ROOT, str(doc_id))
    os.makedirs(d, exist_ok=True)
    return d

def _split_sentences(text: str) -> List[str]:
    text = (text or "").strip()
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    return [s.strip() for s in sents if s and len(s.strip()) > 0]

def chunk_text(text: str, chunk_chars: int = 800, overlap: int = 120) -> List[str]:
    """Pravi chunkove otprilike ~chunk_chars koristeći rečenice i prozor sa overlapom."""
    sents = _split_sentences(text)
    if not sents:
        return [text[:chunk_chars]]

    chunks = []
    buf = ""
    for s in sents:
        if len(buf) + len(s) + 1 <= chunk_chars:
            buf = (buf + " " + s).strip()
        else:
            if buf:
                chunks.append(buf)
            if overlap > 0 and chunks:
                tail = chunks[-1][-overlap:]
                buf = (tail + " " + s).strip()
            else:
                buf = s
    if buf:
        chunks.append(buf)
    return chunks

def _paths(doc_id: int):
    d = _doc_dir(doc_id)
    return {
        "emb": os.path.join(d, "embeddings.npy"),
        "meta": os.path.join(d, "meta.json")
    }

def build_index(doc_id: int, text: str, chunk_chars=800, overlap=120) -> Dict:
    """Napravi/overwrite indeks za dati dokument. Vraća meta info."""
    chunks = chunk_text(text, chunk_chars=chunk_chars, overlap=overlap)
    model = _get_model()
    embs = model.encode(chunks, convert_to_numpy=True, normalize_embeddings=True)

    p = _paths(doc_id)
    np.save(p["emb"], embs)
    with open(p["meta"], "w", encoding="utf-8") as f:
        json.dump({"chunks": chunks}, f, ensure_ascii=False)

    return {"doc_id": doc_id, "chunks": len(chunks)}

def has_index(doc_id: int) -> bool:
    p = _paths(doc_id)
    return os.path.exists(p["emb"]) and os.path.exists(p["meta"])

def ensure_index(doc_id: int, text: str):
    if not has_index(doc_id):
        build_index(doc_id, text)

def _load(doc_id: int):
    p = _paths(doc_id)
    embs = np.load(p["emb"])
    meta = json.load(open(p["meta"], "r", encoding="utf-8"))
    chunks = meta["chunks"]
    return embs, chunks

def retrieve(doc_id: int, query: str, top_k: int = 5) -> List[Dict]:
    """Vrati top_k chunkova sa skorom."""
    if not has_index(doc_id):
        return []

    embs, chunks = _load(doc_id)
    model = _get_model()
    qv = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
    sims = cosine_similarity(qv, embs)[0]  # (N,)
    idxs = np.argsort(-sims)[:max(1, top_k)]
    out = []
    for i in idxs:
        out.append({"text": chunks[int(i)], "score": float(sims[int(i)])})
    return out

def build_context(doc_id: int, query: str, top_k: int = 5, max_chars: int = 3000) -> str:
    """Spoji top_k chunkova u jedan kontekst (ograniči dužinu)."""
    hits = retrieve(doc_id, query, top_k=top_k) or []
    combined = "\n\n".join(h["text"] for h in hits)
    return combined[:max_chars] if combined else ""
