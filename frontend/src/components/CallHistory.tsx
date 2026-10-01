import { useState } from 'react';

import {
  getSavedCall,
  listSavedCalls,
  retrySavedAnalysis,
} from '../services/historyApi';
import type { CallDetail, CallSummary } from '../types/history';
import AnalysisResults from './AnalysisResults';
import ErrorMessage from './ErrorMessage';
import ScoreBreakdown from './ScoreBreakdown';
import ScoreCard from './ScoreCard';

function CallHistory() {
  const [calls, setCalls] = useState<CallSummary[]>([]);
  const [selected, setSelected] = useState<CallDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setCalls(await listSavedCalls());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'History failed.');
    } finally {
      setLoading(false);
    }
  }

  async function select(callId: string) {
    setError(null);
    try {
      setSelected(await getSavedCall(callId));
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'Call detail failed.',
      );
    }
  }

  async function retry() {
    if (!selected) return;
    await retrySavedAnalysis(selected.call_id);
    setSelected(await getSavedCall(selected.call_id));
  }

  return (
    <section
      aria-labelledby="history-heading"
      className="rounded-2xl border border-slate-800 bg-slate-950/40 p-5 sm:p-6"
    >
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold" id="history-heading">
            Saved call history
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Local demo data; no user access control.
          </p>
        </div>
        <button
          className="rounded-lg border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800"
          disabled={loading}
          onClick={() => void refresh()}
          type="button"
        >
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>
      {error && (
        <div className="mt-4">
          <ErrorMessage message={error} />
        </div>
      )}
      {calls.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500">No saved calls loaded.</p>
      ) : (
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {calls.map((call) => (
            <li key={call.call_id}>
              <button
                className="w-full rounded-lg border border-slate-800 p-3 text-left hover:border-sky-500"
                onClick={() => void select(call.call_id)}
                type="button"
              >
                <span className="block text-sm font-medium">
                  {new Date(call.created_at).toLocaleString()}
                </span>
                <span className="text-xs text-slate-500">
                  {call.status} · analysis {call.analysis_status}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {selected && (
        <div className="mt-6 space-y-4 border-t border-slate-800 pt-5">
          {!selected.transcript_complete && (
            <p className="rounded-lg bg-amber-400/10 p-3 text-sm text-amber-200">
              This transcript may be incomplete.
            </p>
          )}
          {(selected.analysis_status === 'pending' ||
            selected.analysis_status === 'running') && (
            <p className="text-sm text-sky-200">
              Post-call analysis is {selected.analysis_status}.
            </p>
          )}
          {selected.analysis_status === 'failed' && (
            <div>
              <ErrorMessage
                message={
                  selected.analysis_error ?? 'Post-call analysis failed.'
                }
              />
              <button
                className="mt-2 rounded-lg bg-sky-500 px-3 py-2 text-sm font-semibold text-slate-950"
                onClick={() => void retry()}
                type="button"
              >
                Retry analysis
              </button>
            </div>
          )}
          {selected.analysis && (
            <>
              <div className="grid gap-4 lg:grid-cols-2">
                <ScoreCard score={selected.analysis.score} />
                <ScoreBreakdown breakdown={selected.analysis.score.breakdown} />
              </div>
              <AnalysisResults
                analysis={selected.analysis.analysis}
                transcript={selected.analysis.transcript}
              />
            </>
          )}
          {!selected.analysis && (
            <details>
              <summary className="cursor-pointer text-sm text-slate-300">
                Final transcript ({selected.transcript_segments.length} turns)
              </summary>
              <div className="mt-2 space-y-2">
                {selected.transcript_segments.map((segment) => (
                  <p
                    className="text-sm text-slate-400"
                    key={segment.segment_id}
                  >
                    <span className="mr-2 text-xs uppercase text-slate-600">
                      Unknown speaker
                    </span>
                    {segment.text}
                  </p>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </section>
  );
}

export default CallHistory;
