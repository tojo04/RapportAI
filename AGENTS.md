# RapportAI — Codex Instructions

## 1. Project goal

Build a small, interview-friendly AI application that analyzes a recorded sales call.

The application must allow a user to:

1. Upload an MP3 or WAV sales-call recording.
2. Transcribe the recording.
3. Extract structured sales information from the transcript.
4. Calculate an explainable call-quality score.
5. View the transcript, analysis, score, and score breakdown in a React interface.

The project should demonstrate practical AI engineering without becoming a production-scale platform.

---

## 2. Required technology stack

### Frontend

- React
- Vite
- TypeScript
- Tailwind CSS
- Native `fetch` or a small API client module
- Vitest and React Testing Library

### Backend

- Python 3.11+
- FastAPI
- Uvicorn
- OpenAI Python SDK
- Pydantic
- `python-multipart`
- `python-dotenv`
- Pytest

### Development tools

- Git
- ESLint
- Prettier


---

## 3. Scope

### Required features

- MP3 and WAV upload
- File validation
- Audio transcription
- Structured transcript analysis
- Deterministic score out of 100
- Score category and component breakdown
- Loading states
- Error states
- Clear results dashboard
- Backend and frontend tests
- Setup documentation

### Explicitly out of scope

Do not add any of the following unless explicitly requested:

- Authentication
- User accounts
- Database
- Payment processing
- Real-time calling
- WebSockets
- Live transcription
- Vector database
- Retrieval-augmented generation
- Fine-tuning
- Microservices
- Docker or Kubernetes
- Redis, Kafka, or background workers
- Analytics platform
- Admin dashboard
- Complex state-management libraries

---

## 4. Repository structure

Use the following structure:

```text
RapportAI/
├── AGENTS.md
├── BUILD_STEPS.md
├── README.md
├── .gitignore
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── index.css
│   │   ├── components/
│   │   │   ├── AudioUploader.tsx
│   │   │   ├── AnalysisResults.tsx
│   │   │   ├── ScoreCard.tsx
│   │   │   ├── ScoreBreakdown.tsx
│   │   │   └── ErrorMessage.tsx
│   │   ├── services/
│   │   │   └── api.ts
│   │   ├── types/
│   │   │   └── analysis.ts
│   │   └── test/
│   │       └── setup.ts
│   └── tests/
└── backend/
    ├── requirements.txt
    ├── .env.example
    ├── app/
    │   ├── __init__.py
    │   ├── main.py
    │   ├── api/
    │   │   ├── __init__.py
    │   │   └── routes.py
    │   ├── models/
    │   │   ├── __init__.py
    │   │   └── analysis.py
    │   ├── services/
    │   │   ├── __init__.py
    │   │   ├── transcription.py
    │   │   └── analysis.py
    │   ├── scoring/
    │   │   ├── __init__.py
    │   │   └── calculator.py
    │   └── core/
    │       ├── __init__.py
    │       └── config.py
    └── tests/
        ├── test_health.py
        ├── test_models.py
        ├── test_scoring.py
        └── test_analyze_route.py
```

Do not create additional layers without a clear need.

---

## 5. Application architecture

Use this data flow:

```text
React upload form
    ↓
POST /api/analyze-call
    ↓
FastAPI validates and stores a temporary file
    ↓
Transcription service converts audio to text
    ↓
Analysis service extracts structured information
    ↓
Pydantic validates the model output
    ↓
Python scoring function calculates the final score
    ↓
FastAPI returns one JSON response
    ↓
React renders the result dashboard
```

The frontend must never call the OpenAI API directly.

---

## 6. Backend responsibilities

### `app/main.py`

- Create the FastAPI application.
- Configure CORS for the local Vite frontend.
- Register API routes.
- Expose a health-check endpoint.
- Contain no OpenAI-specific logic.

### `app/api/routes.py`

- Define the upload endpoint.
- Validate the uploaded file.
- Coordinate transcription, analysis, and scoring.
- Convert internal exceptions into appropriate HTTP responses.
- Always clean up temporary files.
- Contain minimal business logic.

### `app/services/transcription.py`

- Accept a local audio-file path.
- Call the configured transcription model.
- Return a non-empty transcript string.
- Reject missing or empty files.
- Contain no FastAPI or frontend code.

### `app/services/analysis.py`

- Accept a transcript string.
- Send it to the configured text model.
- Request structured output matching the Pydantic schema.
- Return a validated `CallAnalysis` object.
- Never calculate the final score.
- Never invent fallback analysis data when parsing fails.

### `app/scoring/calculator.py`

- Contain a pure deterministic scoring function.
- Make no API calls.
- Return the total, category, and component breakdown.
- Be fully unit-tested.

### `app/models/analysis.py`

Define and validate all request-independent response models.

---

## 7. Required analysis schema

Use Pydantic models equivalent to the following conceptual structure:

```text
ObjectionResponse
- objection: string
- response: string | null

CallAnalysis
- summary: string
- customer_needs: list[string]
- questions_asked: list[string]
- objections: list[ObjectionResponse]
- follow_up_actions: list[string]
- sentiment: positive | neutral | mixed | negative
- next_step_confirmed: boolean
- objection_handling_quality: integer from 0 to 5
- discovery_quality: integer from 0 to 5
- communication_clarity: integer from 0 to 5

ScoreBreakdown
- discovery: integer
- objection_handling: integer
- communication_clarity: integer
- confirmed_next_step: integer
- follow_up_actions: integer

ScoreResult
- total: integer from 0 to 100
- category: Excellent | Good | Needs Improvement | Poor
- breakdown: ScoreBreakdown

AnalyzeCallResponse
- transcript: string
- analysis: CallAnalysis
- score: ScoreResult
```

Frontend TypeScript types must match the backend response shape.

---

## 8. Scoring rules

Calculate the total score deterministically:

- Discovery quality: maximum 25 points
- Objection handling quality: maximum 25 points
- Communication clarity: maximum 20 points
- Confirmed next step: 20 points
- At least one follow-up action: 10 points

Convert the three 0–5 quality ratings proportionally:

```text
discovery = discovery_quality / 5 × 25
objection_handling = objection_handling_quality / 5 × 25
communication_clarity = communication_clarity / 5 × 20
```

Use integer results and document the rounding method.

Categories:

- 85–100: Excellent
- 70–84: Good
- 50–69: Needs Improvement
- 0–49: Poor

The LLM must not directly determine the final score or category.

---

## 9. API contract

### Health check

```http
GET /api/health
```

Expected response:

```json
{
  "status": "ok"
}
```

### Analyze call

```http
POST /api/analyze-call
Content-Type: multipart/form-data
```

Form field:

```text
file: MP3 or WAV file
```

Expected success response:

```json
{
  "transcript": "...",
  "analysis": {
    "summary": "...",
    "customer_needs": [],
    "questions_asked": [],
    "objections": [],
    "follow_up_actions": [],
    "sentiment": "neutral",
    "next_step_confirmed": false,
    "objection_handling_quality": 0,
    "discovery_quality": 0,
    "communication_clarity": 0
  },
  "score": {
    "total": 0,
    "category": "Poor",
    "breakdown": {
      "discovery": 0,
      "objection_handling": 0,
      "communication_clarity": 0,
      "confirmed_next_step": 0,
      "follow_up_actions": 0
    }
  }
}
```

Use a consistent error shape:

```json
{
  "detail": "Human-readable error message"
}
```

---

## 10. File-validation rules

- Accept only `.mp3` and `.wav` files.
- Validate both extension and content type where practical.
- Reject empty files.
- Set a reasonable maximum upload size.
- Do not trust the original filename when creating temporary paths.
- Never keep uploaded audio after the request completes.
- Clean up the temporary file in a `finally` block.

---

## 11. LLM-analysis rules

The analysis prompt must instruct the model to:

- Use only evidence contained in the transcript.
- Never invent customer needs, objections, responses, or next steps.
- Use empty lists when information is absent.
- Distinguish an objection from a normal question.
- Set an objection response to `null` when the salesperson did not answer it.
- Evaluate quality ratings based only on the conversation.
- Keep summaries concise and factual.
- Return output that exactly matches the schema.

Store model instructions in a named constant, not inside route logic.

---

## 12. Frontend responsibilities

### `App.tsx`

- Own the main page layout and top-level request state.
- Coordinate file selection and API submission.
- Render loading, error, empty, and success states.
- Avoid becoming a large all-in-one component.

### `AudioUploader.tsx`

- Allow MP3 and WAV selection.
- Display the selected filename.
- Prevent submission with no selected file.
- Show basic client-side validation errors.

### `AnalysisResults.tsx`

- Render the summary, transcript, customer needs, questions, objections, follow-ups, and sentiment.
- Handle empty arrays gracefully.

### `ScoreCard.tsx`

- Display the total score and category prominently.

### `ScoreBreakdown.tsx`

- Show each scoring component and its maximum value.
- Keep the visualisation simple and explainable.

### `services/api.ts`

- Contain all network-request code.
- Export a typed `analyzeCall(file)` function.
- Parse FastAPI error responses.
- Throw useful frontend errors.

---

## 13. UI requirements

Use a clean single-page dashboard with:

- Project title and one-sentence description
- Upload card
- Analyze button
- Visible loading state
- Overall score card
- Score breakdown
- Summary
- Sentiment
- Customer needs
- Questions asked
- Objections and responses
- Follow-up actions
- Expandable or clearly separated transcript

Keep the design professional but simple. Do not spend excessive time on animations or custom visual effects.

The interface must remain usable on mobile and desktop.

---

## 14. Configuration and secrets

Backend environment variables:

```env
OPENAI_API_KEY=
OPENAI_TRANSCRIPTION_MODEL=
OPENAI_ANALYSIS_MODEL=
MAX_UPLOAD_MB=20
FRONTEND_ORIGIN=http://localhost:5173
```

Rules:

- Never commit `.env`.
- Commit only `.env.example`.
- Never print API keys.
- Never return secrets in HTTP responses.
- Read configuration through one settings module.
- Fail clearly at startup or request time when required configuration is missing.

---

## 15. Coding standards

### Python

- Use type annotations.
- Keep functions focused and short.
- Use descriptive names.
- Prefer explicit control flow over clever abstractions.
- Use Pydantic for structured data validation.
- Use dependency injection or mocking boundaries where useful for tests.
- Do not catch `Exception` unless re-raising or translating it meaningfully.
- Do not silently ignore failures.

### TypeScript and React

- Enable strict TypeScript checking.
- Avoid `any`.
- Use typed props and API responses.
- Prefer functional components.
- Keep API code outside UI components.
- Do not introduce global state libraries for this project.
- Avoid unnecessary `useEffect` usage.
- Show user-facing errors instead of only logging them.

---

## 16. Testing requirements

### Backend

Tests must cover:

- Health endpoint
- Valid and invalid Pydantic data
- Sentiment validation
- Quality-rating bounds
- Score component calculations
- Score category boundaries
- Unsupported file types
- Empty uploads
- Successful analyze route using mocked services
- Service failure translated into an HTTP error
- No test may call a real external API

### Frontend

Tests must cover at least:

- Upload button disabled without a file
- Accepted file selection
- API loading state
- Error message rendering
- Successful analysis rendering
- Empty result lists render correctly

Run all tests before declaring a task complete.

---

## 17. Codex working rules

For every task:

1. Read this file first.
2. Inspect the relevant existing files before editing.
3. State a brief implementation plan.
4. Change only files needed for the task.
5. Do not rewrite unrelated code.
6. Add or update tests for behavior changes.
7. Run the relevant checks.
8. Report:
   - files changed
   - behavior implemented
   - tests run
   - any unresolved issue

Do not claim a command passed unless it was actually run successfully.

---

## 18. Change-control rules

Ask before:

- Changing the required stack
- Adding a dependency not already approved
- Changing the API response shape
- Adding a database
- Adding authentication
- Adding deployment infrastructure
- Reorganizing the repository substantially

Do not ask before making minor implementation decisions that remain within this document.

---

## 19. Definition of done

The project is complete when:

- A user can upload a valid MP3 or WAV file through React.
- FastAPI transcribes and analyzes it.
- The model response is validated by Pydantic.
- Python calculates a deterministic score.
- React displays all returned information clearly.
- Invalid files and API failures produce useful messages.
- Temporary audio files are removed.
- Frontend and backend tests pass.
- The README contains exact local setup instructions.
- No secret or generated environment file is committed.
- The code is small enough for the developer to explain file by file.
