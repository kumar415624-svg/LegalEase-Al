from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import settings
from .utils.text import sanitize_text


class DocumentRequest(BaseModel):
    """Validated payload accepted by POST /generate."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_type: str = Field(..., min_length=2, max_length=settings.max_document_type)
    parties: str = Field(..., min_length=2, max_length=settings.max_parties)
    terms: str = Field(..., min_length=2, max_length=settings.max_terms)
    dates: str = Field(..., min_length=2, max_length=settings.max_dates)

    @field_validator("document_type", "parties", "terms", "dates")
    @classmethod
    def clean_fields(cls, value: str) -> str:
        cleaned = sanitize_text(value)
        if not cleaned or not cleaned.strip():
            raise ValueError("Field must contain usable text.")
        return cleaned


class DocumentResponse(BaseModel):
    document: str
    document_type: str
    demo_mode: bool = False
    model: str | None = None
