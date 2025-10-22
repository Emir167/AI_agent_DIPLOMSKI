import os, atexit, shutil, tempfile
from dotenv import load_dotenv

# UČITAJ .env NA SAMOM POČETKU
BASE_DIR = os.path.dirname(__file__)
load_dotenv(dotenv_path=os.path.join(BASE_DIR, '.env'))

from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from werkzeug.utils import secure_filename

from services import grader  
import services.planner as planner
import services.coach as coach
import services.rag as rag

from models import (
    Base, Document, Summary,
    Quiz, Question, Flashcard,
)
import services.summarizer as summarizer
import services.quizzer as quizzer
import services.flashcards as fc

RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")
UPLOAD_DIR  = os.path.join(RUNTIME_DIR, 'uploads')
GEN_DIR     = os.path.join(RUNTIME_DIR, 'generated')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(GEN_DIR, exist_ok=True)
rag.set_store_dir(RUNTIME_DIR)  

print("RUNTIME_DIR:", RUNTIME_DIR)
print("UPLOAD_DIR :", UPLOAD_DIR)
print("GEN_DIR    :", GEN_DIR)


for folder in [UPLOAD_DIR, GEN_DIR]:
    for f in os.listdir(folder):
        file_path = os.path.join(folder, f)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception:
            pass


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


app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev')
DB_PATH = os.path.join(RUNTIME_DIR, 'studyplatform.db')
engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
Session = scoped_session(sessionmaker(bind=engine))

Base.metadata.create_all(engine)

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
    session = Session()
    session.query(Document).delete()
    session.commit()

    for f in os.listdir(UPLOAD_DIR):
        file_path = os.path.join(UPLOAD_DIR, f)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception:
            pass
    if request.method == 'POST':
        
        file = request.files.get('file')
        if not file or not file.filename:
            flash('Izaberite PDF ili TXT fajl.')
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
        rag.ensure_index(doc.id, doc.content)
        flash('File uploaded successfully.')
        return redirect(url_for('tools'))

    return render_template('upload.html')

@app.get('/tools')
def tools():
    return render_template('tools.html')

# ============== SUMMARIES ==============

@app.route('/summaries/create/<int:doc_id>', methods=['GET','POST'])
def create_summary(doc_id):
    s = Session()
    doc = s.get(Document, doc_id)
    if not doc:
        flash('Document not found.')
        return redirect(url_for('tools'))

    data = summarizer.summarize_via_rag(doc.id, doc.content, query="", max_chunks=5, top_k=5)

    sm = Summary(
        document_id=doc.id,
        title=data['title'],
        text=data['summary'],
        word_count=data['word_count']
    )
    s.add(sm); s.commit()
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

    items, used_ctx, used_provider = quizzer.generate_from_rag(doc.id, doc.content, cfg, user_hint=request.form.get("hint",""))


    quiz = Quiz(document_id=doc.id, title='Kviz', total_questions=len(items))
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
    return render_template('quiz_view.html', quiz=quiz)



@app.get('/quiz/<int:quiz_id>')
def quiz_view(quiz_id):
    s = Session()
    quiz = s.get(Quiz, quiz_id)
    if not quiz:
        flash('Kviz nije pronadjen.')
        return redirect(url_for('tools'))
    return render_template('quiz_view.html', quiz=quiz)

@app.post('/quiz/grade/<int:quiz_id>')
def quiz_grade(quiz_id):
    s = Session()
    quiz = s.get(Quiz, quiz_id)
    if not quiz:
        flash('Kviz nije pronadjen.')
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

    s.query(Flashcard).filter_by(document_id=doc.id).delete(synchronize_session=False)
    s.flush() 

    cards = fc.make_cards_from_rag(doc.id, doc.content, n)

    for c in cards:
        s.add(Flashcard(document_id=doc.id, front=c['front'], back=c['back']))

    s.commit()
    flash(f'Generated {len(cards)} flashcards.')
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



@app.get('/planner')
def planner_form():
    return render_template('planner_form.html')

@app.post('/planner/generate')
def planner_generate():
    level          = (request.form.get('level') or 'Undergraduate').strip()
    learning_style = (request.form.get('learning_style') or 'mixed').strip()
    goals          = (request.form.get('goals') or '').strip()
    notes          = (request.form.get('notes') or '').strip()
    start_time     = (request.form.get('start_time') or '13:00').strip()
    end_time       = (request.form.get('end_time') or '03:00').strip()
    daily_minutes  = int(request.form.get('daily_minutes') or 360)
    days           = int(request.form.get('days') or 10)
    ask            = (request.form.get('ask') or '').strip()

    if not ask:
        flash("Unesi svoj zahtev/opis (npr. Šta spremaš, koliko strana, rok...)")
        return redirect(url_for('planner_form'))

    profile = {
        "level": level,
        "learning_style": learning_style,
        "goals": goals,
        "notes": notes,
        "start_time": start_time,
        "end_time": end_time,
        "daily_minutes": daily_minutes,
        "days": days,
    }

    plan_text = planner.generate_personal_plan(profile, ask)
    return render_template('planner_result.html', plan=plan_text, profile=profile, ask=ask)

@app.get('/coach')
def coach_view():
    return render_template('coach.html')

@app.post('/coach')
def coach_ask():
    q = (request.form.get('q') or '').strip()
    if not q:
        flash("Pitaj nešto.")
        return redirect(url_for('coach_view'))
    s = Session()
    doc = s.query(Document).order_by(Document.created_at.desc()).first()
   # plan = s.query(StudyPlan).order_by(StudyPlan.id.desc()).first()
    #plan_info = f"{plan.start_date}→{plan.end_date}, strategy {plan.strategy}" if plan else "no plan"
    plan_info = 'no plan'
    ans = coach.answer(q, doc.content if doc else "", plan_info, doc_id=doc.id if doc else None)

    return render_template('coach.html', q=q, a=ans)

if __name__ == '__main__':
    app.run(debug=True)
