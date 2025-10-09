import os
from flask import Flask, render_template, request, jsonify, url_for
from werkzeug.utils import secure_filename
from config import Config
from agents.research_agent import run_lit_review
from werkzeug.utils import secure_filename
from datetime import datetime
from db import db, ping
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError
from datetime import datetime
from rag_simple import search as rag_search, answer_from_chunks, get_index

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


mongo_client = None
mongo_db = None
journal_col = None
JOURNAL_ITEMS = []  # i dalje držimo fallback memorijsku listu

def init_mongo():
    """Pokušaj konekcije i podešavanja kolekcija; fallback ako ne uspe."""
    global mongo_client, mongo_db, journal_col
    if app.config.get("USE_MONGO", "1") != "1":
        print("[Mongo] USE_MONGO=0 -> preskačem konekciju (fallback memorija).")
        return
    if journal_col is not None:
        return  # već inicijalizovano

    try:
        mongo_client = MongoClient(
            app.config["MONGODB_URI"],
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
        )
        # ping da proverimo da li mongod radi
        mongo_client.admin.command("ping")

        mongo_db = mongo_client[app.config["MONGO_DB_NAME"]]
        journal_col = mongo_db["journal"]
        journal_col.create_index([("timestamp", ASCENDING)])
        print("[Mongo] Konekcija OK, index kreiran ili već postoji.")
    except Exception as e:
        # Nemoj da rušiš app; samo prijavi i ostani u fallback režimu
        mongo_client = None
        mongo_db = None
        journal_col = None
        print(f"[Mongo] Nije moguće povezati se ({e}). Koristim fallback memoriju.")


@app.before_request
def _startup():
    init_mongo()

# -----------------------
# Pomoćne
# -----------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

def subject_folder(subject_id: int) -> str:
    folder = os.path.join(app.config["UPLOAD_FOLDER"], str(subject_id))
    os.makedirs(folder, exist_ok=True)
    return folder

# -----------------------
# HTML stranice
# -----------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/predmet")
def subjects_list():
    return render_template("predmet.html")

@app.route("/predmet/<int:id>")
def subject_detail(id):
    return render_template("predmet_detalji.html", subject_id=id)

@app.route("/quiz/preview")
def quiz_preview():
    return render_template("quiz_preview.html")

@app.get("/research-assistant/")
def research_assistant_page():
    return render_template("research_assistant.html")

# -----------------------
# API — Predmet dokumenti
# -----------------------
@app.post("/api/predmet/<int:id>/upload")
def upload_documents(id):
    if "files" not in request.files:
        return jsonify({"ok": False, "error": "No files field provided"}), 400

    files = request.files.getlist("files")
    saved = []
    folder = subject_folder(id)

    for f in files:
        if f and allowed_file(f.filename):
            fname = secure_filename(f.filename)
            save_path = os.path.join(folder, fname)
            f.save(save_path)
            saved.append({
                "name": fname,
                "url": url_for("static", filename=f"predmet_documents/{id}/{fname}", _external=False)
            })

    return jsonify({"ok": True, "saved": saved, "count": len(saved)})

@app.get("/api/predmet/<int:id>/documents")
def list_documents(id):
    folder = subject_folder(id)
    files = []
    if os.path.exists(folder):
        for fname in sorted(os.listdir(folder)):
            full = os.path.join(folder, fname)
            if os.path.isfile(full):
                files.append({
                    "name": fname,
                    "url": url_for("static", filename=f"predmet_documents/{id}/{fname}", _external=False)
                })
    return jsonify({"ok": True, "files": files, "count": len(files)})


@app.delete("/api/predmet/<int:id>/documents/<path:filename>")
def delete_document(id, filename):
    safe_name = secure_filename(filename)
    if safe_name != filename:
        return jsonify({"ok": False, "error": "Invalid filename"}), 400

    folder = subject_folder(id)
    file_path = os.path.join(folder, safe_name)

    # os.path.commonpath zaštita
    if os.path.commonpath([os.path.abspath(file_path), os.path.abspath(folder)]) != os.path.abspath(folder):
        return jsonify({"ok": False, "error": "Invalid path"}), 400

    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({"ok": True, "message": f"{safe_name} deleted"})
    return jsonify({"ok": False, "error": "File not found"}), 404


# -----------------------
# API — Research Assistant (stub)
# -----------------------
@app.post("/api/research-assistant/run")
def research_assistant_run():
    data = request.get_json() or {}
    query = (data.get("query") or "").strip()
    md = run_lit_review(query)
    return jsonify({"ok": True, "markdown": md})


# -----------------------
# API — Health & Chat stubs (opciono korisno)
# -----------------------
@app.get("/health")
def health():
    return jsonify(ok=True)

@app.post("/api/chat/general")
def chat_general():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    return jsonify({"response": f"(Stub) Primio sam: {user_msg}"})


@app.post("/api/timetable/generate")
def timetable_generate():
    """
    Stub: generiše primer rasporeda (kasnije ubacujemo tvoj TimetableAgentSystem).
    """
    data = request.get_json() or {}
    timeframe = (data.get("timeframe") or "next 7 days").strip()
    scope = (data.get("scope") or "").strip()

    # primer: 3 sesije
    from datetime import datetime, timedelta
    start = datetime.utcnow() + timedelta(days=1)
    sessions = []
    topics = ["Algebra - Linear Systems", "Data Structures - Trees", "Algorithms - Sorting"]

    for i, topic in enumerate(topics):
        day = start + timedelta(days=i)
        sessions.append({
            "day": day.strftime("%A"),
            "date": day.strftime("%Y-%m-%d"),
            "time": "09:00 - 10:30",
            "start_time": "09:00",
            "end_time": "10:30",
            "topics": [topic],
            "activities": ["Read notes", "Practice problems"],
            "duration": 90,
            "priority": "medium",
            "has_conflict": False,
            "conflict_details": None
        })

    return jsonify({
        "overview": f"Study plan for {timeframe}. Focus: {scope or 'General'}",
        "timetable": sessions,
        "conflicts_summary": "No conflicts detected."
    })


@app.post("/api/timetable/ics")
def timetable_ics():
    """
    Kreira minimalni .ics iz JSON-a poslatog sa fronta.
    Ne koristi eksterne biblioteke (ručno pravimo VCALENDAR).
    """
    data = request.get_json() or {}
    sessions = data.get("timetable", [])

    def ics_escape(s):
        return (s or "").replace(",", r"\,").replace(";", r"\;").replace("\n", r"\n")

    from datetime import datetime
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AI Study Buddy//Timetable//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for i, s in enumerate(sessions):
        # očekujemo YYYY-MM-DD i HH:MM (24h)
        date = s.get("date")
        st = (s.get("start_time") or "09:00").replace(":", "")
        et = (s.get("end_time") or "10:00").replace(":", "")
        if date:
            dtstart = f"{date.replace('-', '')}T{st}00Z"
            dtend = f"{date.replace('-', '')}T{et}00Z"
        else:
            # fallback: danas
            today = datetime.utcnow().strftime("%Y%m%d")
            dtstart = f"{today}T090000Z"
            dtend = f"{today}T100000Z"

        summary = "Study: " + (", ".join(s["topics"]) if isinstance(s.get("topics"), list) else str(s.get("topics", "")))
        desc_parts = []
        if s.get("activities"):
            acts = s["activities"]
            desc_parts.append("Activities: " + (", ".join(acts) if isinstance(acts, list) else str(acts)))
        if s.get("has_conflict"):
            desc_parts.append("CONFLICT: " + (s.get("conflict_details") or "Yes"))

        desc = ics_escape("\n".join(desc_parts))

        lines += [
            "BEGIN:VEVENT",
            f"UID:tt-{i}-{now}",
            f"DTSTAMP:{now}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{ics_escape(summary)}",
            f"DESCRIPTION:{desc}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    ics_text = "\r\n".join(lines) + "\r\n"

    from flask import Response
    return Response(
        ics_text,
        mimetype="text/calendar",
        headers={"Content-Disposition": "attachment; filename=study_timetable.ics"}
    )

# In-memory "baza" za demo
JOURNAL_ITEMS = []

@app.get("/api/journal")
def journal_list():
    init_mongo()  # ako slučajno nije inicijalizovano
    if journal_col:
        try:
            docs = list(journal_col.find().sort("timestamp", ASCENDING))
            items = [
                {
                    "text": d.get("text", ""),
                    "subject_id": d.get("subject_id"),
                    "timestamp": d.get("timestamp"),
                }
                for d in docs
            ]
            return jsonify({"ok": True, "items": items})
        except PyMongoError as e:
            print(f"[Mongo] read error: {e}")
            # graceful degrade:
    # fallback:
    return jsonify({"ok": True, "items": JOURNAL_ITEMS})

@app.post("/api/journal")
def journal_add():
    init_mongo()
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    subject_id = data.get("subject_id")
    if not text:
        return jsonify({"ok": False, "error": "Text is required"}), 400

    item = {
        "text": text,
        "subject_id": subject_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if journal_col:
        try:
            journal_col.insert_one(item.copy())
            return jsonify({"ok": True, "item": item})
        except PyMongoError as e:
            print(f"[Mongo] write error: {e}")
            # padamo na fallback

    # fallback memorija
    JOURNAL_ITEMS.insert(0, item)
    return jsonify({"ok": True, "item": item})

@app.get("/timetable")
def timetable_page():
    return render_template("timetable.html")

@app.get("/journal")
def journal_page():
    return render_template("journal.html")



@app.post("/api/quiz/generate")
def quiz_generate():
    data = request.get_json() or {}
    topic = (data.get("topic") or "General").strip()
    count = max(1, min(30, int(data.get("count") or 5)))
    qtype = (data.get("type") or "mcq").lower()
    difficulty = (data.get("difficulty") or "medium").lower()

    from random import randint, choice
    questions = []

    for i in range(count):
        if qtype == "tf":
            ans = choice(["True","False"])
            questions.append({
                "id": i+1,
                "type": "tf",
                "question": f"[{difficulty}] ({topic}) Statement {i+1}: ... ?",
                "answer": ans,
                "explanation": "Stub: explain why."
            })
        elif qtype == "short":
            questions.append({
                "id": i+1,
                "type": "short",
                "question": f"[{difficulty}] ({topic}) Define concept {i+1}.",
                "answer": "Stub answer",
                "explanation": "Stub: short guidance."
            })
        else:  # mcq
            choices = ["Option A","Option B","Option C","Option D"]
            correct = randint(0, len(choices)-1)
            questions.append({
                "id": i+1,
                "type": "mcq",
                "question": f"[{difficulty}] ({topic}) Question {i+1}?",
                "choices": choices,
                "answer_index": correct,
                "answer_label": chr(65+correct),
                "explanation": "Stub: correct option rationale."
            })

    return jsonify({"ok": True, "questions": questions, "meta": {
        "topic": topic, "count": count, "type": qtype, "difficulty": difficulty
    }})


import random

@app.get("/api/motivational")
def motivational():
    quotes = [
        "Mali koraci, veliki napredak.",
        "Doslednost pobeđuje motivaciju.",
        "Uči pametno, ne samo dugo.",
        "Svaki dan +1% je ogroman pomak za mesec dana.",
        "Greške su dokaz da pokušavaš."
    ]
    return jsonify({"ok": True, "value": random.choice(quotes)})




# ensure upload root exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# --- Mongo connection ---
mongo_client = MongoClient(app.config["MONGODB_URI"])
db = mongo_client[app.config["MONGO_DB_NAME"]]

journal_col = db["journals"]
# indeks (nije obavezno, ali je zgodno)
journal_col.create_index([("timestamp", ASCENDING)])



@app.get("/api/db/ping")
def db_ping():
    try:
        r = ping()
        return jsonify({"ok": True, "result": r})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/research-assistant/search")
def ra_search():
    """
    Body: { "subject_id": 1, "query": "..." , "rebuild": false? }
    """
    data = request.get_json() or {}
    subject_id = int(data.get("subject_id") or 0)
    query = (data.get("query") or "").strip()
    rebuild = bool(data.get("rebuild") or False)
    if not subject_id or not query:
        return jsonify({"ok": False, "error": "subject_id i query su obavezni"}), 400

    results = rag_search(subject_id, query, top_k=5, force_rebuild=rebuild)
    # za front: vraćamo kratke snippete
    items = []
    for r in results:
        items.append({
            "score": r["score"],
            "file": r["meta"]["file"],
            "snippet": (r["chunk"][:400] + "…") if len(r["chunk"]) > 400 else r["chunk"]
        })
    return jsonify({"ok": True, "results": items})

@app.post("/api/research-assistant/qa")
def ra_qa():
    """
    Body: { "subject_id": 1, "question": "..." }
    """
    data = request.get_json() or {}
    subject_id = int(data.get("subject_id") or 0)
    question = (data.get("question") or "").strip()
    if not subject_id or not question:
        return jsonify({"ok": False, "error": "subject_id i question su obavezni"}), 400

    # top 3 chunk-a
    res = rag_search(subject_id, question, top_k=3)
    chunks = [r["chunk"] for r in res]
    ans = answer_from_chunks(question, chunks)

    payload = {
        "ok": True,
        "answer": ans,
        "evidence": [
            {
                "file": r["meta"]["file"],
                "score": r["score"],
                "snippet": (r["chunk"][:400] + "…") if len(r["chunk"]) > 400 else r["chunk"]
            }
            for r in res
        ]
    }
    return jsonify(payload)

# -----------------------
# MAIN
# -----------------------
if __name__ == "__main__":
    print("Flask app pokrenuta na: http://127.0.0.1:5000")
    app.run(debug=True)
