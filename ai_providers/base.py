from abc import ABC, abstractmethod

class AIProvider(ABC):
    @abstractmethod
    def summarize(self, text: str) -> dict:
        """Return {title, summary, word_count}."""

    # Generate quiz questions from given text chunk using model.
    @abstractmethod
    def generate_quiz(self, text: str, config: dict) -> list:
        """
        Return list[{
          kind: 'mcq'|'tf'|'short'|'fill',
          difficulty: 'easy'|'medium'|'hard',
          prompt: str,
          options?: 'A) ...|B) ...|C) ...|D) ...',
          correct: str,
          explanation: str
        }]
        """

    # Judge freeform answers (short/fill) using model.
    @abstractmethod
    def grade_freeform(self, question: str, ground_truth: str, user_answer: str) -> dict:
        """
        Return {correct: bool, reason: str}
        """
