# Knowledge retrieval

RapportAI performs exact pgvector cosine search only against the atomically published active corpus. Results include distance, stable chunk ID, source path/heading, text, content revision, and corpus revision.

The default distance threshold is `0.35`. This is an engineering starting point, not a confidence score; it requires empirical tuning with representative labeled calls. Fake SHA vectors prove ordering, filtering, version isolation, and reproducibility only—not semantic retrieval quality.

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\query_knowledge.py --fake "What does Growth cost?"
```

Use `--real` only after ingesting a real-vector corpus with the same configured model and dimensions. It is a billable opt-in.
