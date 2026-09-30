from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend import routes
from backend.main import app

client = TestClient(app)


def _settings_with(**overrides):
    original = routes.settings
    values = original.__dict__.copy()
    values.update(overrides)
    return SimpleNamespace(**values)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"].startswith("LegalEase")


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model"]
    assert isinstance(body["fallback_models"], list)


def test_validation_rejects_blank_fields():
    response = client.post(
        "/generate",
        json={"document_type": "", "parties": "x", "terms": "y", "dates": "z"},
    )
    assert response.status_code == 422


def test_validation_rejects_unknown_extra_fields():
    response = client.post(
        "/generate",
        json={
            "document_type": "Agreement",
            "parties": "A and B",
            "terms": "Payment; Confidentiality",
            "dates": "2026-09-24",
            "unexpected": "should fail",
        },
    )
    assert response.status_code == 422


def test_validation_rejects_overlong_input():
    response = client.post(
        "/generate",
        json={
            "document_type": "Agreement",
            "parties": "A and B",
            "terms": "x" * 20001,
            "dates": "2026-09-24",
        },
    )
    assert response.status_code == 422


def test_random_weird_but_valid_input_does_not_crash_in_demo(monkeypatch):
    monkeypatch.setattr(routes, "settings", _settings_with(demo_mode=True))
    payload = {
        "document_type": "??? weird contract 🚀",
        "parties": "12345 !!! <tag> \n second party",
        "terms": "@@@; ###; **bold-like**; emoji 😀",
        "dates": "sometime-ish / 2026?",
    }
    response = client.post("/generate", json=payload)
    assert response.status_code == 200
    assert response.json()["document"]


def test_demo_generation(monkeypatch):
    monkeypatch.setattr(routes, "settings", _settings_with(demo_mode=True))
    response = client.post(
        "/generate",
        json={
            "document_type": "Non-Disclosure Agreement",
            "parties": "Jane Doe (Disclosing Party), TechNova Inc. (Receiving Party)",
            "terms": "Confidentiality; Return materials within 30 days; 15 days termination notice",
            "dates": "September 23, 2026",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["document_type"] == "Non-Disclosure Agreement"
    assert "Non-Disclosure Agreement" in body["document"]
    assert body["demo_mode"] is True


def test_live_provider_failure_becomes_stable_502(monkeypatch):
    monkeypatch.setattr(routes, "settings", _settings_with(demo_mode=False))

    def fail(*args, **kwargs):
        raise RuntimeError("No model access")

    monkeypatch.setattr(routes.generator, "generate_document", fail)
    response = client.post(
        "/generate",
        json={
            "document_type": "Agreement",
            "parties": "Alice and Bob",
            "terms": "Payment within 30 days",
            "dates": "2026-09-24",
        },
    )
    assert response.status_code == 502
    assert "No model access" in response.json()["detail"]
