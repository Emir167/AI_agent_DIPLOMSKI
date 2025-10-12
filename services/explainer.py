from ai_providers.local_stub import LocalStub

_provider = LocalStub()

def explain(topic: str):
    return _provider.explain_topic(topic)
