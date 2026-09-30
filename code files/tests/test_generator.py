from types import SimpleNamespace

import backend.ai_core.gemini_generator as gg
from backend.ai_core.gemini_generator import GeminiDocumentGenerator


class _FakeTypes:
    class GenerateContentConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs


class _FakeModels:
    def __init__(self):
        self.calls = []

    def list(self):
        return [
            SimpleNamespace(name="models/gemini-3.8-flash", supported_actions=["generateContent"]),
            SimpleNamespace(name="models/gemini-3.7-flash", supported_actions=["generateContent"]),
            SimpleNamespace(name="models/gemini-embedding-2", supported_actions=["embedContent"]),
        ]

    def generate_content(self, *, model, contents, config):
        self.calls.append(model)
        if model == "gemini-3.8-flash":
            raise RuntimeError("404 NOT_FOUND retired for this account")
        return SimpleNamespace(text="# Agreement\n\n## Terms\nThis is **bold**.")


def test_generator_discovers_only_generate_models_and_falls_back(monkeypatch):
    fake_models = _FakeModels()
    fake_client = SimpleNamespace(models=fake_models)
    generator = GeminiDocumentGenerator(
        api_key="test-key",
        model_name="auto",
        fallback_models=("gemini-3.7-flash",),
        retry_count=0,
    )
    monkeypatch.setattr(gg, "types", _FakeTypes)
    monkeypatch.setattr(generator, "_client_or_raise", lambda: fake_client)

    document = generator.generate_document("Agreement", "A and B", "Payment", "2026-09-24")

    assert "# Agreement" in document
    assert fake_models.calls == ["gemini-3.8-flash", "gemini-3.7-flash"]
    assert generator.last_model_used == "gemini-3.7-flash"
