# Sales Call Analyzer

Sales Call Analyzer is a small AI application that will turn an MP3 or WAV sales-call recording into a transcript, structured sales insights, and an explainable quality score.

The project is being built incrementally. The current scaffold includes a React frontend and a FastAPI backend with a health endpoint. Upload, transcription, analysis, and scoring will be added in later milestones.

## Technology stack

- Frontend: React, Vite, TypeScript, Tailwind CSS, Vitest, and React Testing Library
- Backend: Python 3.11+, FastAPI, Pydantic, the OpenAI Python SDK, and Pytest

## Prerequisites

- Node.js 20 or newer
- Python 3.11 or newer

## Backend setup

From PowerShell:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`. Check it with `GET http://localhost:8000/api/health`.

## Frontend setup

In a second PowerShell terminal:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`.

## Tests and checks

Backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
```

Frontend:

```powershell
cd frontend
npm run test
npm run lint
npm run typecheck
npm run build
```

## Environment variables

Backend variables are documented in `backend/.env.example`. The frontend API base URL is documented in `frontend/.env.example`. Never commit populated `.env` files.
