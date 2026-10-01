# English, Hindi, and Hinglish evaluation

RapportAI preserves Unicode and instructs detection/coaching to understand code-switching. Suggestions follow the latest evidence language: English for English, Hindi for Devanagari Hindi, and natural Hinglish for Hinglish. Grounding and citation rules do not change by language. Language labels can be uncertain and are not speaker identities.

The checked-in fixtures cover questions, price objections, a competitor, an implementation requirement, negation, and no-signal chat. Automated checks prove Unicode roundtrip and exact evidence spans with supplied labels; they do not measure model accuracy. The billable real text evaluation is explicitly opt-in:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\evaluate_multilingual.py --real
```

Audio/STT language accuracy is separate and has not been measured here. For a consented or synthetic smoke test, run one English, one Hindi, and one Hinglish clip through the documented streaming smoke path, retain no audio, and record exact model/config/results. The mixed microphone remains `unknown` speaker. No diarization, role guessing, or talk ratio is implemented.
