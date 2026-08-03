# RapportAI — Codex Build Steps

This file contains the recommended order for building the project with Codex.

The project uses:

- React + Vite + TypeScript + Tailwind CSS for the frontend
- FastAPI + Python for the backend
- OpenAI APIs for transcription and structured analysis
- Pydantic for response validation
- Deterministic Python scoring

Build one task at a time. Review the diff, run the project, run tests, and create a Git commit before moving to the next task.

---

## 0. Final product

The completed application will work like this:

```text
User uploads MP3/WAV
        ↓
React sends multipart request
        ↓
FastAPI validates the file
        ↓
Audio is transcribed
        ↓
Transcript is analyzed into structured data
        ↓
Python calculates an explainable score
        ↓
React displays results
```

The result screen should contain:

- Transcript
- Call summary
- Customer needs
- Questions asked
- Objections
- Salesperson responses
- Follow-up actions
- Sentiment
- Call-quality score
- Component score breakdown

---

## 1. Create the repository

Run:

```powershell
mkdir RapportAI
cd RapportAI
git init
code .
```

Copy `AGENTS.md` and this file into the repository root.

Create an initial checkpoint:

```powershell
git add AGENTS.md BUILD_STEPS.md
git commit -m "docs: add project instructions and build plan"
```

---

## 2. Task 1 — Scaffold the monorepo

### Codex prompt

```text
Read AGENTS.md completely before making changes.

Create the initial RapportAI repository structure.

Frontend requirements:
- React
- Vite
- TypeScript
- Tailwind CSS
- Vitest
- React Testing Library

Backend requirements:
- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic
- OpenAI Python SDK
- python-dotenv
- python-multipart
- pytest
- httpx for FastAPI tests

Create the folder structure specified in AGENTS.md.

For this task only:
- The React page should show the project title and description.
- FastAPI should expose GET /api/health returning {"status": "ok"}.
- Configure CORS for http://localhost:5173 through an environment setting.
- Add .env.example and .gitignore files.
- Add initial frontend and backend tests.
- Add a root README with basic placeholder setup sections.

Do not implement file upload, transcription, analysis, or scoring yet.
Do not add a database or authentication.

Run the available tests and report all commands and results.
```

### Expected result

- Frontend opens successfully.
- Backend starts successfully.
- `/api/health` works.
- Frontend and backend tests run.

### Local commands

Backend:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend, in another terminal:

```powershell
cd frontend
npm install
npm run dev
```

### Verification

Open:

```text
Frontend: http://localhost:5173
Backend docs: http://localhost:8000/docs
Health: http://localhost:8000/api/health
```

### Commit

```powershell
git add .
git commit -m "chore: scaffold React and FastAPI application"
```

---

## 3. Task 2 — Define the backend data models

Create the structured data contract before making any model API call.

### Codex prompt

```text
Read AGENTS.md and inspect the current backend.

Implement the Pydantic models in backend/app/models/analysis.py.

Required models:

1. ObjectionResponse
- objection: non-empty string
- response: string or null

2. CallAnalysis
- summary: non-empty string
- customer_needs: list of strings
- questions_asked: list of strings
- objections: list of ObjectionResponse
- follow_up_actions: list of strings
- sentiment: positive, neutral, mixed, or negative
- next_step_confirmed: boolean
- objection_handling_quality: integer from 0 to 5
- discovery_quality: integer from 0 to 5
- communication_clarity: integer from 0 to 5

3. ScoreBreakdown
- discovery
- objection_handling
- communication_clarity
- confirmed_next_step
- follow_up_actions

4. ScoreResult
- total: integer from 0 to 100
- category: Excellent, Good, Needs Improvement, or Poor
- breakdown: ScoreBreakdown

5. AnalyzeCallResponse
- transcript
- analysis
- score

Add tests for:
- valid model construction
- invalid sentiment
- ratings below 0 or above 5
- invalid score total
- invalid category
- required non-empty fields

Do not implement scoring or OpenAI calls in this task.
Run backend tests when finished.
```

### Concepts to understand

Before continuing, be able to explain:

- Why Pydantic validation is needed for LLM output
- Difference between a Python dictionary and a validated model
- Why the API response needs a stable schema
- How a TypeScript frontend benefits from a stable backend contract

### Commit

```powershell
git add backend
git commit -m "feat: add structured analysis response models"
```

---

## 4. Task 3 — Implement deterministic scoring

The language model will provide small 0–5 assessments. Python will produce the final score.

### Codex prompt

```text
Read AGENTS.md and inspect the existing analysis models.

Implement backend/app/scoring/calculator.py.

Create this pure function:

calculate_call_score(analysis: CallAnalysis) -> ScoreResult

Use these maximum values:
- Discovery quality: 25
- Objection handling quality: 25
- Communication clarity: 20
- Confirmed next step: 20
- One or more follow-up actions: 10

Convert 0-to-5 quality values proportionally to their maximum values.
Use a documented and consistent integer rounding method.

Score categories:
- 85 to 100: Excellent
- 70 to 84: Good
- 50 to 69: Needs Improvement
- 0 to 49: Poor

Requirements:
- No API calls
- No FastAPI imports
- No side effects
- Full type annotations
- Return a ScoreResult model

Add comprehensive tests for:
- zero score
- maximum score
- each individual component
- category boundaries 49/50, 69/70, and 84/85
- follow-up action present versus absent
- confirmed next step true versus false

Run backend tests.
```

### Important interview explanation

Use this explanation:

> The LLM extracts semantic evidence and provides bounded quality ratings, but the final score is calculated by deterministic business logic. This makes the result reproducible, testable, and easier to audit.

### Commit

```powershell
git add backend
git commit -m "feat: add deterministic call scoring"
```

---

## 5. Task 4 — Implement the transcript-analysis service

Start with a plain transcript. Audio upload is not needed yet.

### Codex prompt

```text
Read AGENTS.md and inspect the backend models and configuration.

Implement backend/app/services/analysis.py.

Requirements:
- Accept a transcript string.
- Reject empty or whitespace-only transcripts.
- Use the OpenAI Python SDK.
- Read the analysis model name from configuration.
- Request structured output matching CallAnalysis.
- Return a validated CallAnalysis object.
- Store the system instructions in a named constant.
- Never calculate the final score in this service.
- Do not silently repair invalid model output.
- Raise a clear service-level exception when analysis fails.
- Never expose API keys or raw internal exception details to API users.

The analysis instructions must require the model to:
- use only evidence in the transcript
- avoid invented facts
- use empty lists when information is absent
- distinguish customer objections from normal questions
- use null when an objection received no response
- make quality judgments only from the transcript
- return data matching the schema exactly

Make the OpenAI client replaceable or mockable in tests.

Add unit tests using mocks. Tests must not make real network requests.
Test:
- successful validated result
- empty transcript rejection
- SDK failure
- invalid structured output

Do not add an HTTP route yet.
Run backend tests.
```

### Manual test option

Create a temporary local script only when useful, or use a Python shell to call the service with a short sample transcript.

Example transcript:

```text
Salesperson: What problem are you trying to solve?
Customer: Our team loses time manually preparing weekly reports.
Salesperson: Our platform automates those reports.
Customer: It sounds useful, but the price may be too high.
Salesperson: We can start with a smaller plan and upgrade later.
Customer: Send me a proposal by Friday.
Salesperson: I will email the proposal tomorrow and call you on Friday.
```

Do not commit real API keys or generated outputs.

### Commit

```powershell
git add backend
git commit -m "feat: add structured transcript analysis service"
```

---

## 6. Task 5 — Implement the transcription service

### Codex prompt

```text
Read AGENTS.md and inspect the backend configuration and service conventions.

Implement backend/app/services/transcription.py.

Requirements:
- Accept a pathlib.Path or clearly typed local path.
- Support MP3 and WAV files.
- Reject missing files.
- Reject empty files.
- Read the transcription model name from configuration.
- Use the OpenAI Audio Transcription API.
- Return a non-empty transcript string.
- Raise a clear service-level exception on failure.
- Do not import FastAPI.
- Do not delete files supplied by the caller.
- Keep the OpenAI client mockable.

Add unit tests using temporary files and mocked API responses.
Tests must cover:
- successful MP3 transcription
- successful WAV transcription
- unsupported extension
- missing file
- empty file
- empty transcription response
- SDK failure

No test may make a real API call.
Run backend tests.
```

### Commit

```powershell
git add backend
git commit -m "feat: add audio transcription service"
```

---

## 7. Task 6 — Implement the analyze-call API endpoint

This task connects validation, temporary-file handling, transcription, analysis, and scoring.

### Codex prompt

```text
Read AGENTS.md and inspect all backend modules.

Implement POST /api/analyze-call in backend/app/api/routes.py.

The endpoint must:
- Accept one multipart form field named file.
- Accept only MP3 and WAV.
- reject empty files.
- Enforce MAX_UPLOAD_MB from configuration.
- Create a safe temporary file without trusting the original filename.
- Call the transcription service.
- Call the transcript-analysis service.
- Calculate the deterministic score.
- Return AnalyzeCallResponse.
- Remove the temporary file in a finally block.
- Return clear HTTP errors.
- Avoid exposing API keys or raw stack traces.

Keep route logic small. Extract validation helpers if needed, but do not over-engineer.

Add API tests using FastAPI TestClient and mocked services.
Tests must cover:
- successful request
- unsupported extension
- empty upload
- oversized upload
- transcription failure
- analysis failure
- expected response shape
- temporary-file cleanup where practical

No test may call a real OpenAI endpoint.
Run all backend tests.
```

### Manual API test

Start the backend:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Use the Swagger UI:

```text
http://localhost:8000/docs
```

Select `POST /api/analyze-call`, upload a short audio file, and execute the request.

### Commit

```powershell
git add backend
git commit -m "feat: add call analysis API endpoint"
```

---

## 8. Task 7 — Define frontend types and API client

Do not begin with the full UI. First make the frontend/backend contract explicit.

### Codex prompt

```text
Read AGENTS.md and inspect the backend response models and current frontend.

Implement the frontend data contract and API client.

In frontend/src/types/analysis.ts, add strict TypeScript types matching:
- ObjectionResponse
- CallAnalysis
- ScoreBreakdown
- ScoreResult
- AnalyzeCallResponse

In frontend/src/services/api.ts, implement:

analyzeCall(file: File): Promise<AnalyzeCallResponse>

Requirements:
- Send multipart/form-data to POST /api/analyze-call.
- Do not manually set the multipart Content-Type boundary.
- Read the backend base URL from a Vite environment variable.
- Parse successful JSON responses.
- Parse FastAPI error responses.
- Throw a useful Error for network, HTTP, and malformed-response failures.
- Do not use any unless absolutely unavoidable.

Add frontend unit tests for:
- successful response
- FastAPI detail error
- network failure
- correct form field name

Do not build the complete results UI yet.
Run frontend tests, linting, and type checking.
```

### Environment file

Frontend `.env.example`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

### Commit

```powershell
git add frontend
git commit -m "feat: add typed frontend API client"
```

---

## 9. Task 8 — Build the upload workflow

### Codex prompt

```text
Read AGENTS.md and inspect the frontend types and API client.

Implement the React audio-upload workflow.

Create or update:
- AudioUploader.tsx
- ErrorMessage.tsx
- App.tsx

Requirements:
- Accept .mp3 and .wav files.
- Display the selected filename and file size.
- Reject unsupported files before submission.
- Disable Analyze Call when no valid file is selected.
- Show a clear loading state while the request is running.
- Prevent duplicate submissions while loading.
- Call analyzeCall(file) from the API service.
- Show user-facing errors.
- Store the successful response in typed React state.
- Do not render the complete result details yet; show a simple success placeholder.
- Keep API code outside React components.
- Make the layout responsive and professional using Tailwind.

Add tests for:
- disabled state with no file
- valid file selection
- invalid extension
- loading state
- successful request
- failed request

Run tests, linting, and type checking.
```

### Commit

```powershell
git add frontend
git commit -m "feat: add audio upload workflow"
```

---

## 10. Task 9 — Build the result dashboard

### Codex prompt

```text
Read AGENTS.md and inspect the AnalyzeCallResponse type and current upload flow.

Implement the complete result dashboard.

Create or update:
- AnalysisResults.tsx
- ScoreCard.tsx
- ScoreBreakdown.tsx
- App.tsx

Display:
- total score out of 100
- score category
- discovery score out of 25
- objection handling score out of 25
- communication clarity score out of 20
- confirmed next step score out of 20
- follow-up action score out of 10
- summary
- sentiment
- customer needs
- questions asked
- objections and responses
- follow-up actions
- transcript

Requirements:
- Render empty lists with a friendly "None identified" message.
- Render an unanswered objection clearly when response is null.
- Make the transcript easy to expand, collapse, or scan.
- Keep score visualization simple; do not add a chart library.
- Use semantic HTML and accessible labels.
- Keep components focused and typed.
- Preserve loading and error behavior.

Add tests for:
- score and category rendering
- component breakdown
- empty lists
- null objection response
- transcript rendering
- sentiment rendering

Run tests, linting, type checking, and the production build.
```

### Commit

```powershell
git add frontend
git commit -m "feat: add sales call result dashboard"
```

---

## 11. Task 10 — Improve reliability and error handling

### Codex prompt

```text
Read AGENTS.md and perform a reliability review of both frontend and backend.

Inspect for:
- invalid or oversized files
- temporary files not removed
- OpenAI failures
- malformed structured output
- empty transcripts
- duplicate frontend submissions
- stale result state after a failed request
- environment variables missing
- overly broad exception handling
- secrets exposed in logs or responses
- CORS configuration issues
- mismatch between Python models and TypeScript types

First report the findings with severity and file locations.
Then fix only high- and medium-severity findings.
Do not add unrelated features or new infrastructure.
Add regression tests for every fixed behavior.
Run the complete backend and frontend verification suites.
```

### Commit

```powershell
git add .
git commit -m "fix: improve upload and analysis reliability"
```

---

## 12. Task 11 — Complete the README

### Codex prompt

```text
Read AGENTS.md and inspect the complete repository.

Rewrite README.md as accurate project documentation.

Include:
- project overview
- problem being solved
- feature list
- architecture diagram using Mermaid
- technology stack
- repository structure
- prerequisites
- backend setup commands for Windows PowerShell
- frontend setup commands
- environment variable setup
- how to run frontend and backend
- how to run tests
- API endpoint documentation
- deterministic scoring formula
- explanation of structured output validation
- limitations
- possible future improvements
- short interview explanation of the architecture

Only document behavior that actually exists in the repository.
Do not claim deployment, authentication, databases, or real-time support.
```

### Commit

```powershell
git add README.md
git commit -m "docs: complete setup and architecture documentation"
```

---

## 13. Task 12 — Final code review

### First Codex prompt: review only

```text
Read AGENTS.md and perform a strict final review of the entire repository.

Do not modify files yet.

Review for:
- secrets accidentally committed
- incorrect OpenAI SDK usage
- API response validation gaps
- temporary-file leaks
- unsafe filename handling
- upload-size enforcement bugs
- frontend/backend type mismatches
- business logic inside React components
- business logic inside FastAPI routes
- tests that make real network calls
- tests that do not test meaningful behavior
- missing loading and error states
- inaccessible UI controls
- unnecessary dependencies
- dead code
- code that is too complex to explain in an interview

Return findings ordered by severity.
For each finding include:
- severity
- file and symbol
- exact problem
- practical consequence
- recommended correction
```

### Second Codex prompt: fix findings

```text
Fix the high- and medium-severity findings from the previous review.

Constraints:
- Do not add new product features.
- Do not change the public API shape unless required to fix a correctness problem.
- Do not perform unrelated refactoring.
- Add regression tests for fixed defects.
- Run all backend and frontend checks.
- Report each changed file and the command results.
```

### Final commit

```powershell
git add .
git commit -m "chore: complete final quality review"
```

---

## 14. Required verification commands

### Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest
```

Optionally add linting and formatting if configured:

```powershell
ruff check .
ruff format --check .
```

### Frontend

```powershell
cd frontend
npm run test
npm run lint
npm run typecheck
npm run build
```

If `typecheck` is not defined, use:

```powershell
npx tsc --noEmit
```

### Manual end-to-end verification

1. Start the backend.
2. Start the frontend.
3. Upload a short WAV file.
4. Confirm the loading state appears.
5. Confirm a transcript is returned.
6. Confirm all structured sections render.
7. Confirm score components add to the total.
8. Upload an invalid file and confirm a useful error appears.
9. Refresh and repeat with another audio file.
10. Check that no uploaded audio remains in the repository.

---

## 15. How to review Codex changes

After every task:

```text
1. Read Codex's summary.
2. Open every changed file.
3. Inspect the Git diff.
4. Ask for explanations of unfamiliar code.
5. Run the feature manually.
6. Run relevant tests.
7. Commit only when the task works.
```

Useful Git commands:

```powershell
git status
git diff
git diff --staged
git log --oneline --decorate -10
```

Never accept a change merely because the code looks plausible.

---

## 16. Prompts for understanding the generated code

After each task, give Codex this prompt:

```text
Explain the code added in the previous task as if I must defend it in a technical interview.

For every changed file explain:
1. Its responsibility.
2. Important functions, classes, and types.
3. Input and output data.
4. Why this implementation was selected.
5. One reasonable alternative.
6. Failure cases.
7. How the tests verify it.
8. Questions an interviewer may ask.

Use concrete references to the current code.
```

Then use:

```text
Quiz me on this implementation one question at a time.
Do not reveal the answer until I respond.
Focus on React, TypeScript, FastAPI, Pydantic, multipart uploads,
temporary files, mocked tests, structured LLM output, and deterministic scoring.
```

---

## 17. Features to add only after the core project works

Choose at most one of these as an optional extension:

### Option A — Speaker labels

Display salesperson and customer labels when supported by the transcription output.

### Option B — Downloadable report

Allow the user to download the completed analysis as JSON or a simple PDF.

### Option C — Demo mode

Provide a sample transcript that can be analyzed without uploading audio.

### Option D — Conversation timeline

Group detected needs, objections, and follow-up commitments in conversation order.

Do not implement optional features until the required end-to-end workflow is complete and tested.

---

## 18. Project completion checklist

- [ ] React frontend loads.
- [ ] FastAPI backend loads.
- [ ] Health endpoint works.
- [ ] MP3 and WAV files can be selected.
- [ ] Invalid file types are rejected.
- [ ] Upload-size limit works.
- [ ] Audio transcription works.
- [ ] Transcript analysis returns validated structured data.
- [ ] Final score is deterministic.
- [ ] Score breakdown adds up correctly.
- [ ] All result sections render.
- [ ] Empty results render gracefully.
- [ ] Temporary files are removed.
- [ ] No API key is committed.
- [ ] Backend tests pass.
- [ ] Frontend tests pass.
- [ ] Type checking passes.
- [ ] Frontend production build passes.
- [ ] README setup steps are accurate.
- [ ] You can explain every major file.

---

## 19. Two-minute interview explanation

Use this structure when presenting the project:

```text
I built a sales-call analysis application with a React frontend and a FastAPI backend.
The user uploads an MP3 or WAV file, which is sent as multipart form data to FastAPI.
The backend stores it only temporarily and sends it to a transcription model.
The resulting transcript is passed to a second model that returns structured sales information matching a Pydantic schema.
I validate the model output instead of trusting free-form text.
The final quality score is not generated directly by the model; it is calculated using deterministic Python logic, which makes it testable and explainable.
The backend returns one typed JSON response, and React displays the score, breakdown, summary, needs, objections, follow-ups, and transcript.
I also added mocked tests so the test suite does not make paid external API calls.
```

Be prepared to explain why:

- the frontend does not call OpenAI directly
- Pydantic validation is required
- temporary files are cleaned up
- scoring is deterministic
- external API calls are mocked in tests
- no database was needed for the MVP
