from ai_providers.local_stub import LocalStub

_provider = LocalStub()

def make_cards(text: str, n: int):
    return _provider.make_flashcards(text, n)
