"""
Stub verzija research agenta — kasnije ćemo je povezati s RAG/LLM logikom.
"""
import random

def run_lit_review(query: str) -> str:
    examples = [
        f"### Literature Review: {query}\n\n1. Research by Smith et al. (2023) explored key methods...\n2. Recent findings suggest integrating adaptive AI agents in education...\n\n_This is an auto-generated summary._",
        f"## Analysis of recent works on '{query}'\n\n- Paper A (2022): Focused on neural architectures.\n- Paper B (2023): Discussed LangChain-based learning agents.\n\n_Summary complete._",
    ]
    return random.choice(examples)
