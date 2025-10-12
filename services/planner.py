# services/planner.py
from datetime import date, timedelta, datetime

def _str2date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

def estimate_pages(doc) -> int:
    if getattr(doc, 'page_count', 0):
        return max(1, int(doc.page_count))
    # TXT: gruba procena
    words = len((doc.content or "").split())
    return max(1, words // 300)  # ~300 w/str

def build_plan(doc, profile, start_date: str, end_date: str, daily_minutes: int = 90, strategy="1-3-7"):
    sd, ed = _str2date(start_date), _str2date(end_date)
    days = (ed - sd).days + 1
    pages = estimate_pages(doc)
    diff = max(1, min(3, getattr(doc, 'difficulty', 2)))
    weight = {1: 0.9, 2: 1.0, 3: 1.25}[diff]

    # koliko strana/dan (gruba linearna podela skalirana tezinom)
    pages_per_day = max(1, int(round((pages * weight) / max(1, days))))

    # preferirani prozor
    window = f"{profile.pref_start}-{profile.pref_end}"

    sessions = []
    assigned = 0
    cur = sd
    while cur <= ed and assigned < pages:
        chunk = min(pages_per_day, pages - assigned)
        sessions.append({
            "date": cur.isoformat(),
            "window": window,
            "topic": "New material",
            "kind": "learn",
            "target_pages": chunk
        })
        # spacing za ovaj chunk
        offs = []
        if strategy == "1-3-7":
            offs = [1, 3, 7]
        for d in offs:
            rday = cur + timedelta(days=d)
            if sd <= rday <= ed:
                sessions.append({
                    "date": rday.isoformat(),
                    "window": window,
                    "topic": "Review",
                    "kind": "review",
                    "target_pages": chunk // 3 or 1
                })
        assigned += chunk
        cur += timedelta(days=1)

    # quiz dan: 80% puta prema kraju
    if sessions:
        quiz_day = sd + timedelta(days=int(0.8 * max(1, days-1)))
        sessions.append({
            "date": quiz_day.isoformat(),
            "window": window,
            "topic": "Practice Quiz",
            "kind": "quiz",
            "target_pages": 0
        })
    # sortiraj po datumu + vrati plan meta
    sessions.sort(key=lambda x: x["date"])
    return {"pages": pages, "sessions": sessions}
