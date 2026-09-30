from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE)


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _csv_models(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _as_positive_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "LegalEase").strip() or "LegalEase"
    app_version: str = os.getenv("APP_VERSION", "1.2.0").strip() or "1.2.0"
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    # Google currently documents Gemini 3.8 Flash as a stable text-generation model.
    gemini_model: str = os.getenv("GEMINI_MODEL", "auto").strip() or "auto"
    gemini_fallback_models: tuple[str, ...] = _csv_models(
        os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash")
    )
    demo_mode: bool = _as_bool(os.getenv("DEMO_MODE"), default=False)
    backend_url: str = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").strip().rstrip("/")
    max_document_type: int = _as_positive_int(os.getenv("MAX_DOCUMENT_TYPE"), 150, 10, 500)
    max_parties: int = _as_positive_int(os.getenv("MAX_PARTIES"), 2500, 50, 10000)
    max_terms: int = _as_positive_int(os.getenv("MAX_TERMS"), 8000, 50, 20000)
    max_dates: int = _as_positive_int(os.getenv("MAX_DATES"), 500, 10, 2000)


settings = Settings()
