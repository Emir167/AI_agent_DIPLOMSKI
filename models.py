from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()
page_count = Column(Integer, default=0)     
difficulty = Column(Integer, default=2)   
class Document(Base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), nullable=False)
    size_kb = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    summaries = relationship('Summary', back_populates='document', cascade='all,delete')
    quizzes   = relationship('Quiz',     back_populates='document', cascade='all,delete')
    flashcards= relationship('Flashcard',back_populates='document', cascade='all,delete')

class Summary(Base):
    __tablename__ = 'summaries'
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    title = Column(String(255), default='Content Summary')
    text = Column(Text, nullable=False)
    word_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship('Document', back_populates='summaries')

# ===== QUIZ =====

class Quiz(Base):
    __tablename__ = 'quizzes'
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    title = Column(String(255), default='Practice Quiz')
    total_questions = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship('Document', back_populates='quizzes')
    questions = relationship('Question', back_populates='quiz', cascade='all,delete')

class Question(Base):
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey('quizzes.id'), nullable=False)
    kind = Column(String(32))         # mcq|tf|short|fill
    difficulty = Column(String(16))   # easy|medium|hard
    prompt = Column(Text, nullable=False)
    options = Column(Text)            # "A) ...|B) ...|C) ...|D) ..."
    correct_answer = Column(Text)     # "A" / "True" / slobodan tekst
    explanation = Column(Text)

    quiz = relationship('Quiz', back_populates='questions')

# ===== FLASHCARDS =====

class Flashcard(Base):
    __tablename__ = 'flashcards'
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    front = Column(Text, nullable=False)
    back  = Column(Text, nullable=False)
    known = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship('Document', back_populates='flashcards')

# (opciono) Planer za ponavljanje
class ReviewSchedule(Base):
    __tablename__ = 'review_schedule'
    id = Column(Integer, primary_key=True)
    card_id = Column(Integer, ForeignKey('flashcards.id'), nullable=False)
    scheduled_for = Column(DateTime, nullable=False)

# --- novi modeli ---
class StudyProfile(Base):
    __tablename__ = 'study_profiles'
    id = Column(Integer, primary_key=True)
    age = Column(Integer, default=20)
    level = Column(String(64), default='Undergraduate') 
    learning_style = Column(String(64), default='mixed') 
    notes = Column(Text, default='')
    goals = Column(Text, default='')                    
    pref_start = Column(String(5), default='18:00')     
    pref_end   = Column(String(5), default='20:00')   

class StudyPlan(Base):
    __tablename__ = 'study_plans'
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    profile_id  = Column(Integer, ForeignKey('study_profiles.id'), nullable=False)
    title = Column(String(255), default='Study Plan')
    start_date = Column(String(10))  
    end_date   = Column(String(10))
    total_pages = Column(Integer, default=0)
    strategy = Column(String(32), default='1-3-7')  
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship('Document')
    profile = relationship('StudyProfile')
    sessions = relationship('StudySession', back_populates='plan', cascade='all,delete')

class StudySession(Base):
    __tablename__ = 'study_sessions'
    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey('study_plans.id'), nullable=False)
    date = Column(String(10), nullable=False)                
    window = Column(String(11), default='18:00-20:00')     
    topic = Column(String(255), default='Study')
    kind  = Column(String(16), default='learn')              
    target_pages = Column(Integer, default=0)
    completed = Column(Boolean, default=False)

    plan = relationship('StudyPlan', back_populates='sessions')