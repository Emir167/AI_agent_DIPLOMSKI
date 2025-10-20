from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

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
