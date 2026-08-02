import { useState } from 'react';

import AnalysisResults from './components/AnalysisResults';
import AudioUploader from './components/AudioUploader';
import ErrorMessage from './components/ErrorMessage';
import ScoreBreakdown from './components/ScoreBreakdown';
import ScoreCard from './components/ScoreCard';
import { analyzeCall } from './services/api';
import type { AnalyzeCallResponse } from './types/analysis';

function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeCallResponse | null>(null);

  function handleFileSelect(file: File | null) {
    setSelectedFile(file);
    setError(null);
    setResult(null);
  }

  async function handleSubmit() {
    if (!selectedFile || isLoading) {
      return;
    }

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await analyzeCall(selectedFile);
      setResult(response);
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'The call could not be analyzed. Please try again.',
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100 sm:px-6 sm:py-16">
      <section className="mx-auto w-full max-w-6xl rounded-3xl border border-slate-800 bg-slate-900/80 p-6 shadow-2xl shadow-sky-950/30 sm:p-10 lg:p-12">
        <p className="mb-4 text-sm font-semibold uppercase tracking-[0.22em] text-sky-400">
          AI-assisted sales coaching
        </p>
        <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
          Sales Call Analyzer
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
          Turn recorded sales conversations into structured insights and an
          explainable call-quality score.
        </p>

        <div className="mt-10 space-y-5">
          <AudioUploader
            isLoading={isLoading}
            onFileSelect={handleFileSelect}
            onSubmit={handleSubmit}
            selectedFile={selectedFile}
          />

          {isLoading && (
            <div
              aria-live="polite"
              className="flex items-center gap-3 rounded-xl border border-sky-400/20 bg-sky-400/10 px-4 py-3 text-sm text-sky-100"
              role="status"
            >
              <span
                aria-hidden="true"
                className="h-4 w-4 animate-spin rounded-full border-2 border-sky-200/30 border-t-sky-200"
              />
              Transcribing and analyzing your call…
            </div>
          )}

          {error && <ErrorMessage message={error} />}

          {result && (
            <section
              aria-labelledby="analysis-complete-heading"
              aria-live="polite"
              className="space-y-6"
            >
              <h2
                className="text-2xl font-semibold text-emerald-100"
                id="analysis-complete-heading"
              >
                Analysis complete
              </h2>
              <div className="grid gap-6 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
                <ScoreCard score={result.score} />
                <ScoreBreakdown breakdown={result.score.breakdown} />
              </div>
              <AnalysisResults
                analysis={result.analysis}
                transcript={result.transcript}
              />
            </section>
          )}
        </div>
      </section>
    </main>
  );
}

export default App;
