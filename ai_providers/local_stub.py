import re
from .base import AIProvider

class LocalStub(AIProvider):
    def _sentences(self, text):
        parts = re.split(r'[\.!\?]\s+', text or '')
        return [p.strip() for p in parts if p and len(p.strip()) > 0]

    def summarize(self, text: str) -> dict:
        sents = self._sentences(text)
        body = ' '.join(sents[:6]) if sents else (text or '')[:600]
        return {'title': 'Content Summary', 'summary': body, 'word_count': len(body.split())}

    def generate_quiz(self, text: str, config: dict) -> list:
        n_mcq  = int(config.get('mcq', 5))
        n_tf   = int(config.get('tf', 5))
        n_short= int(config.get('short', 5))
        n_fill = int(config.get('fill', 5))
        diffs  = [d.lower() for d in config.get('difficulties', ['Easy','Medium','Hard'])]
        out = []
        for i in range(n_mcq):
            out.append({
                'kind':'mcq','difficulty': diffs[i % len(diffs)],
                'prompt':'In a dataset with varying densities, which clustering is most effective?',
                'options':'A) K-Means|B) Hierarchical|C) DBSCAN|D) GMM',
                'correct':'C','explanation':'DBSCAN finds arbitrary shapes and varying densities.'
            })
        for i in range(n_tf):
            out.append({
                'kind':'tf','difficulty': diffs[i % len(diffs)],
                'prompt':'True or False: Logistic regression outputs probabilities via a sigmoid.',
                'options':'A) True|B) False','correct':'A','explanation':'Sigmoid maps to [0,1].'
            })
        for i in range(n_short):
            out.append({
                'kind':'short','difficulty': diffs[i % len(diffs)],
                'prompt':'What does a confusion matrix reveal?',
                'correct':'TP/TN/FP/FN breakdown',
                'explanation':'From it you get precision/recall/F1.'
            })
        for i in range(n_fill):
            out.append({
                'kind':'fill','difficulty': diffs[i % len(diffs)],
                'prompt':'In DBSCAN, points within the specified _____ are neighbors.',
                'correct':'epsilon (eps)','explanation':'Epsilon radius defines neighborhood.'
            })
        return out

    def grade_freeform(self, question: str, ground_truth: str, user_answer: str) -> dict:
        gt = (ground_truth or '').strip().lower()
        ua = (user_answer or '').strip().lower()
        ok = bool(gt and ua and (gt in ua or ua in gt))
        why = "Substring match (stub) — upgrade to model for smarter judging."
        return {'correct': ok, 'reason': why}
    
    def make_flashcards(self, text: str, n: int) -> list:
        sents = self._sentences(text)
        out = []
        for i in range(min(n, max(1, len(sents)))):
            s = sents[i]
            q = f"Objasni ukratko: {s[:80]}..."
            a = s if len(s) < 220 else s[:220] + "..."
            out.append({"front": q, "back": a})
        return out


    def explain_topic(self, topic: str):
        return {
            "title": f"Objašnjenje: {topic}",
            "body": f"Kratak pregled teme '{topic}'. Ovo je lokalni stub bez pravog AI-a.",
        }