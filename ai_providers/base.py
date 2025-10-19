from abc import ABC, abstractmethod
class AIProvider(ABC):
    @abstractmethod
    def summarize(self, text: str) -> dict:
        """Return {title, summary, word_count}."""

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

    @abstractmethod
    def grade_freeform(self, question: str, ground_truth: str, user_answer: str) -> dict:
        """
        Return {correct: bool, reason: str}
        """
