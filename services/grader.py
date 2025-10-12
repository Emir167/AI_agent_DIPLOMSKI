from .quizzer import _get_provider

def grade_freeform(question: str, ground_truth: str, user_answer: str) -> dict:
    return _get_provider().grade_freeform(question, ground_truth, user_answer)
