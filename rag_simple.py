# rag_simple.py
import os, re, time
from collections import defaultdict
from typing import List, Dict, Any, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DOC_ROOT = os.path.join("static", "predmet_documents")

# vrlo prost cache po subject_id (da ne indeksiramo stalno)
_INDEX_CACHE: Dict[str, Dict[str, Any]] = {}

def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""

def _collect_docs_for_subject(subject_id: int) -> List[Tuple[str, str]]:
    """
    Vraća listu (filename, text) za .txt i .md fajlove.
    """
    folder = os.path.join(DOC_ROOT, str(subject_id))
    docs = []
    if not os.path.isdir(folder):
        return docs
    for fname in sorted(os.listdir(folder)):
        ext = os.path.splitext(fname)[1].lower()
        if ext in [".txt", ".md"]:
            full = os.path.join(folder, fname)
            text = _read_text_file(full)
            if text.strip():
                docs.append((fname, text))
    return docs

def _make_chunks(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """
    Prosto chunk-ovanje po rečima, bez NLP teških biblioteka.
    """
    words = re.split(r"\s+", text)
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i+chunk_size]
        if not chunk:
            break
        chunks.append(" ".join(chunk))
        i += (chunk_size - overlap)
    return chunks

def build_index(subject_id: int) -> Dict[str, Any]:
    """
    Kreira TF-IDF indeks nad chunkovima svih fajlova za dati predmet.
    """
    all_chunks = []
    meta = []  # prate info: (fname, local_chunk_idx)
    docs = _collect_docs_for_subject(subject_id)

    for fname, text in docs:
        chunks = _make_chunks(text)
        for idx, ch in enumerate(chunks):
            all_chunks.append(ch)
            meta.append({"file": fname, "chunk_idx": idx})

    if not all_chunks:
        # prazan indeks
        vectorizer = TfidfVectorizer()
        matrix = vectorizer.fit_transform([""])
        return {"vectorizer": vectorizer, "matrix": matrix, "chunks": [], "meta": [], "built_at": time.time()}

    vectorizer = TfidfVectorizer(stop_words="english")
    matrix = vectorizer.fit_transform(all_chunks)
    return {
        "vectorizer": vectorizer,
        "matrix": matrix,
        "chunks": all_chunks,
        "meta": meta,
        "built_at": time.time(),
    }

def get_index(subject_id: int, force_rebuild: bool = False) -> Dict[str, Any]:
    key = str(subject_id)
    if force_rebuild or key not in _INDEX_CACHE:
        _INDEX_CACHE[key] = build_index(subject_id)
    return _INDEX_CACHE[key]

def search(subject_id: int, query: str, top_k: int = 5, force_rebuild: bool = False) -> List[Dict[str, Any]]:
    idx = get_index(subject_id, force_rebuild=force_rebuild)
    if not idx["chunks"]:
        return []

    qv = idx["vectorizer"].transform([query])
    sims = cosine_similarity(qv, idx["matrix"]).ravel()
    order = sims.argsort()[::-1][:top_k]

    results = []
    for rank in order:
        results.append({
            "score": float(sims[rank]),
            "chunk": idx["chunks"][rank],
            "meta": idx["meta"][rank],
        })
    return results

def answer_from_chunks(query: str, chunks: List[str]) -> str:
    """
    Ultra-simplifikovano: vrati kratak 'sažetak' baziran na top chunkovima.
    Ne koristi LLM — čisto heuristika.
    """
    if not chunks:
        return "Nisam našao relevantan deo u dokumentima."
    # uzmi prvu rečenicu iz naj-relevantnijeg chanka
    best = chunks[0]
    sent = re.split(r"(?<=[.!?])\s+", best.strip())
    lead = sent[0] if sent else best[:200]
    return f"Kratak odgovor (heuristika): {lead}"
