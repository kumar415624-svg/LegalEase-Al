from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

from ..config import settings
from ..utils.text import sanitize_text, terms_to_list

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - exercised on machines before installation
    genai = None
    types = None


@dataclass
class GeminiDocumentGenerator:
    """Generate LegalEase drafts using Google's current GenAI SDK.

    The generator uses model discovery when possible, then retries temporary
    provider failures and falls back through current stable text-generation models.
    """

    api_key: str | None = None
    model_name: str | None = None
    fallback_models: tuple[str, ...] | None = None
    retry_count: int = 2
    retry_delay_seconds: float = 1.5

    # Current stable text-generation models documented by Google.
    DEFAULT_MODEL_CANDIDATES = (
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
    )

    def __post_init__(self) -> None:
        self.api_key = (self.api_key or settings.gemini_api_key).strip()
        self.model_name = (self.model_name or settings.gemini_model).strip() or "auto"
        self.fallback_models = tuple(self.fallback_models or settings.gemini_fallback_models)
        self._client = None
        self.last_model_used: str | None = None
        self.last_attempts: list[str] = []

    @staticmethod
    def _is_placeholder_key(value: str | None) -> bool:
        return not value or value.strip() in {
            "PASTE_YOUR_GEMINI_API_KEY_HERE",
            "YOUR_REAL_GEMINI_API_KEY",
            "YOUR_API_KEY_HERE",
        }

    def _client_or_raise(self):
        if self._is_placeholder_key(self.api_key):
            raise RuntimeError(
                "Gemini API key is not configured. Open .env and set GEMINI_API_KEY to your Google AI Studio API key."
            )
        if genai is None:
            raise RuntimeError(
                "The Google GenAI SDK is not installed. Run 'python -m pip install -r requirements.txt'."
            )
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    @staticmethod
    def build_prompt(document_type: str, parties: str, terms: str, dates: str) -> str:
        term_list = terms_to_list(terms)
        terms_block = "\n".join(f"- {item}" for item in term_list) or "- [INSERT AGREED TERMS]"
        return f"""You are LegalEase, an AI-powered legal document generator.

Create a comprehensive professional draft of the requested legal document using only the supplied information.
Do not invent names, addresses, payment amounts, dates, duties, governing law, or any other material facts.
When information is missing, use a clear placeholder in square brackets instead of guessing.
Use formal legal language, clear headings, numbered clauses, and signature blocks where appropriate.
Preserve every user-requested term and incorporate it into a coherent document.

DOCUMENT TYPE:
{sanitize_text(document_type)}

PARTIES INVOLVED:
{sanitize_text(parties)}

EFFECTIVE DATE / DATE DETAILS:
{sanitize_text(dates)}

TERMS & CONDITIONS:
{terms_block}

OUTPUT REQUIREMENTS:
1. Start with the document title as a Markdown H1.
2. Use Markdown H2 headings for major sections.
3. Use numbered clauses where suitable.
4. Include definitions, obligations, confidentiality, payment, term/termination, dispute or governing-law provisions only when relevant and supported by the provided facts; otherwise use placeholders.
5. Include signature sections for the relevant parties.
6. End with a short 'Review Notes' section identifying material missing information or placeholders.
7. Return only the document draft. Do not discuss these instructions.
""".strip()

    def _configured_candidates(self) -> Iterable[str]:
        seen: set[str] = set()
        configured = [self.model_name, *self.fallback_models]
        for name in configured:
            model = (name or "").strip()
            if model and model.lower() != "auto" and model not in seen:
                seen.add(model)
                yield model

    def _available_generate_models(self) -> set[str] | None:
        """Return API-visible text generation model IDs when listing is permitted."""
        client = self._client_or_raise()
        try:
            available: set[str] = set()
            for model in client.models.list():
                name = str(getattr(model, "name", "") or "").strip()
                if not name:
                    continue
                short_name = name.split("/", 1)[1] if name.startswith("models/") else name
                actions = getattr(model, "supported_actions", None)
                if actions is None:
                    actions = getattr(model, "supported_generation_methods", None)
                action_names = {str(item).replace("_", "").lower() for item in (actions or [])}
                if action_names and "generatecontent" not in action_names:
                    continue
                if short_name in self.DEFAULT_MODEL_CANDIDATES or short_name.startswith("gemini-"):
                    available.add(short_name)
            return available or None
        except Exception:
            # Some keys/SDK versions can generate without allowing model listing.
            return None

    def _candidate_models(self) -> list[str]:
        if (self.model_name or "").lower() == "auto":
            configured = list(self.DEFAULT_MODEL_CANDIDATES)
        else:
            configured = list(self._configured_candidates())
            if not configured:
                configured = list(self.DEFAULT_MODEL_CANDIDATES)

        available = self._available_generate_models()
        if not available:
            return configured

        candidates = [name for name in configured if name in available]
        for name in self.DEFAULT_MODEL_CANDIDATES:
            if name in available and name not in candidates:
                candidates.append(name)
        return candidates or configured

    @staticmethod
    def _is_temporary_provider_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(
            token in text
            for token in (
                "429",
                "rate limit",
                "resource exhausted",
                "503",
                "service unavailable",
                "high demand",
                "temporarily unavailable",
                "internal server error",
                "deadline exceeded",
            )
        )

    def generate_document(self, document_type: str, parties: str, terms: str, dates: str) -> str:
        client = self._client_or_raise()
        prompt = self.build_prompt(document_type, parties, terms, dates)
        failures: list[str] = []
        self.last_attempts = []
        self.last_model_used = None

        if types is None:
            raise RuntimeError("The Google GenAI SDK types module is unavailable. Reinstall requirements.txt.")

        config = types.GenerateContentConfig(
            temperature=0.25,
            max_output_tokens=8192,
            system_instruction=(
                "You draft professional legal documents from user-supplied facts. "
                "Never fabricate material facts; use bracketed placeholders for missing information."
            ),
        )

        candidates = self._candidate_models()
        if not candidates:
            raise RuntimeError("No Gemini text-generation model is available for this API key.")

        for model_name in candidates:
            for attempt in range(self.retry_count + 1):
                self.last_attempts.append(f"{model_name} (attempt {attempt + 1})")
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config,
                    )
                    content = sanitize_text(getattr(response, "text", None) or "")
                    if content:
                        self.last_model_used = model_name
                        return content
                    failures.append(f"{model_name}: empty response")
                    break
                except Exception as exc:  # provider errors vary by SDK/API version
                    if self._is_temporary_provider_error(exc) and attempt < self.retry_count:
                        time.sleep(self.retry_delay_seconds * (2**attempt))
                        continue
                    failures.append(f"{model_name}: {exc}")
                    break

        joined = " | ".join(failures)
        raise RuntimeError(
            "Gemini could not generate the document with the available models. "
            "Check your API key, API access, quota, and internet connection. "
            f"Provider details: {joined}"
        )

    @staticmethod
    def demo_document(document_type: str, parties: str, terms: str, dates: str) -> str:
        term_list = terms_to_list(terms)
        party_lines = [part.strip() for part in sanitize_text(parties).split(",") if part.strip()]
        party_text = ", ".join(party_lines) or "[INSERT PARTIES]"
        bullets = "\n".join(f"- {term}" for term in term_list) or "- [INSERT AGREED TERMS]"
        return sanitize_text(
            f"""# {sanitize_text(document_type) or '[LEGAL DOCUMENT]'}

## 1. Parties
{party_text}

## 2. Effective Date
{sanitize_text(dates) or '[INSERT EFFECTIVE DATE]'}

## 3. Purpose
This draft records the principal terms supplied by the parties for the {sanitize_text(document_type) or 'legal document'}.

## 4. Terms & Conditions
{bullets}

## 5. Additional Provisions
The parties should add all provisions required for their transaction and applicable jurisdiction, including any notices, representations, warranties, remedies, intellectual-property provisions, and dispute-resolution terms that are not specified above.

## 6. Signatures

Party 1: ______________________________    Date: __________________

Party 2: ______________________________    Date: __________________

## Review Notes
This is a local demonstration draft. Replace placeholders and review the document carefully before signing or relying on it.
"""
        )
