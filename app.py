import os
from flask import Flask, render_template, request, jsonify, url_for
from werkzeug.utils import secure_filename
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

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
    folder = subject_folder(id)
    file_path = os.path.join(folder, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({"ok": True, "message": f"{filename} deleted"})
    return jsonify({"ok": False, "error": "File not found"}), 404

# -----------------------
# API — Research Assistant (stub)
# -----------------------
@app.post("/api/research-assistant/run")
def research_assistant_run():
    data = request.get_json() or {}
    query = (data.get("query") or "").strip()
    md = f"# Literature Review\n\n**Topic:** {query}\n\n- Point 1\n- Point 2\n\n_This is a stub. Hook up research_agent.run_lit_review next._"
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
    return jsonify({"ok": True, "items": JOURNAL_ITEMS})

@app.post("/api/journal")
def journal_add():
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    subject_id = data.get("subject_id")
    if not text:
        return jsonify({"ok": False, "error": "Text is required"}), 400
    from datetime import datetime
    item = {
        "text": text,
        "subject_id": subject_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
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


# -----------------------
# MAIN
# -----------------------
if __name__ == "__main__":
    print("Flask app pokrenuta na: http://127.0.0.1:5000")
    app.run(debug=True)
