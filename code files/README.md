# LegalEase — AI-Powered Legal Document Generator

LegalEase is the FastAPI + Streamlit + Google Gemini application described in the supplied project documentation. It accepts document type, parties, terms and effective-date details, generates a legal draft, lets the user edit it, previews it with formatting, and exports TXT, DOCX and PDF.

## GitHub-ready setup

This repository contains:

- `.env.example` — safe configuration template with no secret key.
- `.gitignore` — excludes `.env`, `.venv`, caches, generated files and IDE files.
- `.env` — local configuration file only; do not commit it.

The `.env` file is intentionally ignored by Git so a real Gemini API key is not pushed to GitHub.

## Gemini configuration

Google's current Gemini API documentation uses the `google-genai` Python SDK and supports `client.models.generate_content(...)`. LegalEase uses that current SDK. The app defaults to automatic model discovery and uses current stable Gemini text-generation models instead of the retired Gemini 1.5 family.

Create your local `.env` from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Then set your real Google AI Studio key:

```env
GEMINI_API_KEY=PASTE_YOUR_GEMINI_API_KEY_HERE
GEMINI_MODEL=auto
GEMINI_FALLBACK_MODELS=gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash,gemini-3.5-flash-lite
DEMO_MODE=false
BACKEND_URL=http://127.0.0.1:8000
APP_NAME=LegalEase
APP_VERSION=1.2.0
```

`GEMINI_MODEL=auto` first checks models exposed to the key when possible. If model listing is unavailable, it tries the current stable model sequence directly. Temporary 429/503-style provider failures are retried before the next available model is tried.

## VS Code — final terminal steps

Open the extracted `LegalEase` folder in VS Code.

### Terminal 1 — FastAPI backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### Terminal 2 — Streamlit frontend

VS Code → **Terminal → New Terminal**

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run frontend/app.py
```

Open:

```text
http://localhost:8501
```

The FastAPI service remains an internal application component, but backend URL/check controls are not shown to normal users in the frontend.

## Offline UI testing

To test the frontend and all document downloads without using Gemini:

```env
DEMO_MODE=true
```

Then restart the backend.

## Automated testing

```powershell
python -m pytest -q
```

The tests cover:

- FastAPI root and health endpoints.
- Empty, overlong, and extra-field validation.
- Random/unusual Unicode and punctuation inputs in demo mode.
- Stable handling of provider failures as API responses.
- Gemini model discovery and fallback using a mocked provider.
- TXT, DOCX and PDF generation.
- Bold/italic Markdown conversion.
- Unicode PDF export fallback.

## Project structure

```text
LegalEase/
├── .env
├── .env.example
├── .gitignore
├── .streamlit/
│   └── config.toml
├── assets/
│   └── logo.png
├── backend/
│   ├── main.py
│   ├── routes.py
│   ├── schemas.py
│   ├── config.py
│   ├── ai_core/
│   │   └── gemini_generator.py
│   ├── services/
│   │   ├── docx_formatter.py
│   │   ├── pdf_formatter.py
│   │   ├── txt_formatter.py
│   │   └── exporters.py
│   └── utils/
│       └── text.py
├── frontend/
│   └── app.py
├── tests/
├── requirements.txt
├── Dockerfile
├── Procfile
├── run_backend.bat
├── run_backend.sh
├── run_frontend.bat
└── run_frontend.sh
```

## GitHub safety

Do not drag the local `.env` into the GitHub web uploader. Commit the project files and `.env.example`; `.gitignore` protects the real `.env` when using Git locally.
