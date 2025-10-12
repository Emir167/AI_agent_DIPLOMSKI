import os, atexit, shutil, tempfile
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from werkzeug.utils import secure_filename
from services import grader  
import services.planner as planner
import services.coach as coach

from models import (
    Base, Document, Summary,
    Quiz, Question, Flashcard,
        StudyProfile, StudyPlan, StudySession
)
import services.summarizer as summarizer
import services.quizzer as quizzer
import services.flashcards as fc
import services.explainer as explainer
# ...
# ----- setup -----
BASE_DIR = os.path.dirname(__file__)
load_dotenv(dotenv_path=os.path.join(BASE_DIR, '.env'))
# === RUNTIME (privremeni) direktorijum za jednu sesiju ===
RUNTIME_DIR = tempfile.mkdtemp(prefix="studyplatform_")
UPLOAD_DIR  = os.path.join(RUNTIME_DIR, 'uploads')
GEN_DIR     = os.path.join(RUNTIME_DIR, 'generated')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(GEN_DIR, exist_ok=True)

# Opcionalno: ako želiš ponekad da PERSIST-uješ (za debug), setuj env PERSIST_RUN=1
PERSIST_RUN = os.getenv('PERSIST_RUN') == '1'

def _cleanup():
    if not PERSIST_RUN and os.path.isdir(RUNTIME_DIR):
        try:
            shutil.rmtree(RUNTIME_DIR, ignore_errors=True)
        except Exception:
            pass

atexit.register(_cleanup)


import os
print("GROQ_API_KEY set? ->", bool(os.getenv("GROQ_API_KEY")))
print("Using GROQ_MODEL ->", os.getenv("GROQ_MODEL"))
print("OLLAMA_MODEL ->", os.getenv("OLLAMA_MODEL"))


BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
GEN_DIR = os.path.join(BASE_DIR, 'generated')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(GEN_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev')
DB_PATH = os.path.join(RUNTIME_DIR, 'studyplatform.db')
engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
Session = scoped_session(sessionmaker(bind=engine))

# kreiraj tabele (idempotentno)
Base.metadata.create_all(engine)

# sidebar helper
@app.context_processor
def inject_docs():
    s = Session()
    docs = s.query(Document).order_by(Document.created_at.desc()).all()
    return {'sidebar_docs': docs}

# ============== CORE ROUTES ==============

@app.get('/')
def home():
    return redirect(url_for('upload'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename:
            flash('Select a PDF or TXT file.')
            return redirect(url_for('upload'))

        fname = secure_filename(file.filename)
        path = os.path.join(UPLOAD_DIR, fname)
        file.save(path)

        # extract text
        if fname.lower().endswith('.pdf'):
            from services import extract_text
            text = extract_text.from_pdf(path)
        else:
            text = open(path, 'r', encoding='utf-8', errors='ignore').read()

        size_kb = max(1, os.path.getsize(path) // 1024)
        s = Session()
        doc = Document(filename=fname, size_kb=size_kb, content=text)
        s.add(doc)
        s.commit()

        flash('File uploaded successfully.')
        return redirect(url_for('tools'))

    return render_template('upload.html')

@app.get('/tools')
def tools():
    return render_template('tools.html')

# ============== SUMMARIES ==============

@app.route('/summaries/create/<int:doc_id>', methods=['GET', 'POST'])
def create_summary(doc_id):
    s = Session()
    doc = s.get(Document, doc_id)
    if not doc:
        flash('Document not found.')
        return redirect(url_for('tools'))

    data = summarizer.summarize(doc.content)
    sm = Summary(
        document_id=doc.id,
        title=data['title'],
        text=data['summary'],
        word_count=data['word_count']
    )
    s.add(sm)
    s.commit()
    return redirect(url_for('summary_view', summary_id=sm.id))


@app.get('/summaries/<int:summary_id>')
def summary_view(summary_id):
    s = Session()
    sm = s.get(Summary, summary_id)
    if not sm:
        flash('Summary not found.')
        return redirect(url_for('tools'))
    return render_template('summary.html', summary=sm)

@app.get('/summaries/download/<int:summary_id>')
def download_summary(summary_id):
    s = Session()
    sm = s.get(Summary, summary_id)
    if not sm:
        flash('Summary not found.')
        return redirect(url_for('tools'))

    out = os.path.join(GEN_DIR, f'summary_{summary_id}.txt')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(sm.text)
    return send_file(out, as_attachment=True, download_name=os.path.basename(out))

# ============== QUIZ ==============

@app.get('/quiz/config/<int:doc_id>')
def quiz_config(doc_id):
    return render_template('quiz_config.html', doc_id=doc_id)

@app.post('/quiz/generate/<int:doc_id>')
def quiz_generate(doc_id):
    s = Session()
    doc = s.get(Document, doc_id)
    if not doc:
        flash('Document not found.')
        return redirect(url_for('tools'))

    cfg = {
        'mcq': int(request.form.get('mcq', 5)),
        'tf': int(request.form.get('tf', 5)),
        'short': int(request.form.get('short', 5)),
        'fill': int(request.form.get('fill', 5)),
        'difficulties': [
            d for d in ['Easy', 'Medium', 'Hard']
            if request.form.get(d.lower()) == 'on'
        ] or ['Easy', 'Medium', 'Hard']
    }

    items, used_chunk, used_provider = quizzer.generate_from_random_chunk(doc.content, cfg, target_words=350)


    quiz = Quiz(document_id=doc.id, title='Practice Quiz', total_questions=len(items))
    s.add(quiz)
    s.flush()

    for q in items:
        s.add(Question(
            quiz_id=quiz.id,
            kind=q['kind'],
            difficulty=q['difficulty'],
            prompt=q['prompt'],
            options=q.get('options'),
            correct_answer=q.get('correct'),
            explanation=q.get('explanation')
        ))

    s.commit()
    return render_template('quiz_view.html', quiz=quiz, chunk_preview=used_chunk[:400], provider=used_provider)


@app.get('/quiz/<int:quiz_id>')
def quiz_view(quiz_id):
    s = Session()
    quiz = s.get(Quiz, quiz_id)
    if not quiz:
        flash('Quiz not found.')
        return redirect(url_for('tools'))
    return render_template('quiz_view.html', quiz=quiz)

@app.post('/quiz/grade/<int:quiz_id>')
def quiz_grade(quiz_id):
    s = Session()
    quiz = s.get(Quiz, quiz_id)
    if not quiz:
        flash('Quiz not found.')
        return redirect(url_for('tools'))

    correct = 0
    answers = {}
    details = {}  # for explanations/AI reasons

    for q in quiz.questions:
        key = f'q_{q.id}'
        user = (request.form.get(key) or '').strip()
        answers[q.id] = user

        if q.kind in ('mcq', 'tf'):
            ok = (user.upper() == (q.correct_answer or '').upper())
            if ok: correct += 1
            details[q.id] = {"ai": False, "ok": ok, "reason": "Exact match"}
        else:
            # AI grading for short/fill
            res = quizzer.grade_freeform(q.prompt, q.correct_answer or "", user)
            ok = bool(res.get("correct"))
            if ok: correct += 1
            details[q.id] = {"ai": True, "ok": ok, "reason": res.get("reason","")}

    percent = int(round(100 * correct / max(1, len(quiz.questions))))
    return render_template('quiz_view.html',
        quiz=quiz, answers=answers, score=correct, percent=percent, details=details)


# ============== FLASHCARDS ==============

@app.get('/flashcards/config/<int:doc_id>')
def flashcards_config(doc_id):
    return render_template('flashcards_config.html', doc_id=doc_id)

@app.post('/flashcards/create/<int:doc_id>')
def flashcards_create(doc_id):
    s = Session()
    doc = s.get(Document, doc_id)
    if not doc:
        flash('Document not found.')
        return redirect(url_for('tools'))

    n = int(request.form.get('count', 10))
    cards = fc.make_cards(doc.content, n)

    for c in cards:
        s.add(Flashcard(document_id=doc.id, front=c['front'], back=c['back']))
    s.commit()
    return redirect(url_for('flashcards_view', doc_id=doc.id))

@app.get('/flashcards/<int:doc_id>')
def flashcards_view(doc_id):
    s = Session()
    doc = s.get(Document, doc_id)
    if not doc:
        flash('Document not found.')
        return redirect(url_for('tools'))

    cards = s.query(Flashcard).filter_by(document_id=doc.id).order_by(Flashcard.id.asc()).all()
    return render_template('flashcards_view.html', doc=doc, cards=cards)

@app.post('/flashcards/mark/<int:card_id>')
def flashcards_mark(card_id):
    s = Session()
    card = s.get(Flashcard, card_id)
    if card:
        card.known = not card.known
        s.commit()
    return redirect(request.referrer or url_for('tools'))

# ============== EXPLAIN TOPIC ==============

@app.get('/explain')
def explain_topic():
    return render_template('explain_topic.html')

@app.post('/explain')
def explain_topic_post():
    topic = (request.form.get('topic') or '').strip()
    if not topic:
        flash('Enter a topic.')
        return redirect(url_for('explain_topic'))

    data = explainer.explain(topic)
    return render_template('explain_result.html', topic=topic, data=data)

# ------------------------------------------

# ---- PLANNER ----
@app.get('/planner')
def planner_form():
    s = Session()
    docs = s.query(Document).order_by(Document.created_at.desc()).all()
    prof = s.query(StudyProfile).first()
    return render_template('planner_form.html', docs=docs, profile=prof)

@app.post('/planner/create')
def planner_create():
    s = Session()
    doc_id = int(request.form['document_id'])
    start  = request.form['start_date']
    end    = request.form['end_date']
    pref_start = request.form.get('pref_start','18:00')
    pref_end   = request.form.get('pref_end','20:00')
    level = request.form.get('level','Undergraduate')
    learning_style = request.form.get('learning_style','mixed')
    goals = request.form.get('goals','')
    notes = request.form.get('notes','')
    daily_minutes = int(request.form.get('daily_minutes', 90))

    doc = s.get(Document, doc_id)
    if not doc:
        flash("Document not found.")
        return redirect(url_for('planner_form'))

    # profil (jednostavno: uvek kreiramo/azuriramo 1 profil)
    prof = s.query(StudyProfile).first()
    if not prof:
        prof = StudyProfile()
        s.add(prof)
    prof.level = level
    prof.learning_style = learning_style
    prof.goals = goals
    prof.notes = notes
    prof.pref_start = pref_start
    prof.pref_end = pref_end
    s.flush()

    plan_meta = planner.build_plan(doc, prof, start, end, daily_minutes=daily_minutes, strategy="1-3-7")

    sp = StudyPlan(
        document_id=doc.id, profile_id=prof.id, title=f"Plan for {doc.filename}",
        start_date=start, end_date=end, total_pages=plan_meta["pages"], strategy="1-3-7"
    )
    s.add(sp); s.flush()

    for it in plan_meta["sessions"]:
        s.add(StudySession(
            plan_id=sp.id, date=it["date"], window=it["window"],
            topic=it["topic"], kind=it["kind"], target_pages=it["target_pages"]
        ))
    s.commit()
    return redirect(url_for('planner_view', plan_id=sp.id))

@app.get('/planner/<int:plan_id>')
def planner_view(plan_id):
    s = Session()
    plan = s.get(StudyPlan, plan_id)
    if not plan:
        flash("Plan not found.")
        return redirect(url_for('planner_form'))
    sessions = s.query(StudySession).filter_by(plan_id=plan.id).order_by(StudySession.date.asc()).all()
    return render_template('planner_view.html', plan=plan, sessions=sessions)

@app.post('/planner/toggle/<int:session_id>')
def planner_toggle(session_id):
    s = Session()
    ss = s.get(StudySession, session_id)
    if ss:
        ss.completed = not ss.completed
        s.commit()
    return redirect(request.referrer or url_for('planner_view', plan_id=ss.plan_id if ss else 1))


@app.get('/coach')
def coach_view():
    return render_template('coach.html')

@app.post('/coach')
def coach_ask():
    q = (request.form.get('q') or '').strip()
    if not q:
        flash("Ask something.")
        return redirect(url_for('coach_view'))
    s = Session()
    doc = s.query(Document).order_by(Document.created_at.desc()).first()
    plan = s.query(StudyPlan).order_by(StudyPlan.id.desc()).first()
    plan_info = f"{plan.start_date}→{plan.end_date}, strategy {plan.strategy}" if plan else "no plan"
    text = doc.content if doc else ""
    ans = coach.answer(q, text, plan_info)
    return render_template('coach.html', q=q, a=ans)

if __name__ == '__main__':
    app.run(debug=True)
