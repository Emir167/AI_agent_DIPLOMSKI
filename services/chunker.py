import random
import re

def split_into_sentences(text: str):
    parts = re.split(r'(?<=[.!?])\\s+', text or '')
    return [p.strip() for p in parts if p.strip()]

def random_chunk(text: str, target_words: int = 300, overlap: int = 40) -> str:
    sents = split_into_sentences(text)
    if not sents:
        words = (text or "").split()
        if not words:
            return ""
        start = 0 if len(words) <= target_words else random.randint(0, max(0, len(words)-target_words))
        return " ".join(words[start:start+target_words])

    windows = []
    buf = []
    count = 0
    for s in sents:
        w = len(s.split())
        buf.append(s)
        count += w
        if count >= target_words:
            windows.append(" ".join(buf))
            tail_words = " ".join(buf).split()[-overlap:]
            buf = [" ".join(tail_words)]
            count = len(tail_words)
    if not windows:
        windows = [" ".join(sents)]
    return random.choice(windows)
