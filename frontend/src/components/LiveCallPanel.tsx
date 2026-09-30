import { useLiveCall } from '../hooks/useLiveCall';
import ErrorMessage from './ErrorMessage';

function formatElapsed(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes.toString().padStart(2, '0')}:${seconds
    .toString()
    .padStart(2, '0')}`;
}

function formatBytes(bytes: number): string {
  if (bytes < 1_024) return `${bytes} B`;
  return `${(bytes / 1_024).toFixed(1)} KB`;
}

function LiveCallPanel() {
  const liveCall = useLiveCall();
  const isStartingOrLive = ['connecting', 'live', 'stopping'].includes(
    liveCall.status,
  );
  const canStop =
    liveCall.status === 'connecting' || liveCall.status === 'live';

  return (
    <section
      aria-labelledby="live-call-heading"
      className="rounded-2xl border border-emerald-400/30 bg-emerald-400/5 p-5 sm:p-6"
    >
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-300">
            Realtime transport preview
          </p>
          <h2
            className="mt-2 text-lg font-semibold text-white"
            id="live-call-heading"
          >
            Analyze a live conversation
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-400">
            Streams this browser microphone to the backend. This transport test
            does not transcribe audio yet and does not capture a remote meeting
            participant separately.
          </p>
        </div>

        <span
          aria-live="polite"
          className="w-fit rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-300"
        >
          {liveCall.status}
        </span>
      </div>

      <dl className="mt-5 grid grid-cols-3 gap-3 text-sm">
        <div className="rounded-xl bg-slate-950/70 p-3">
          <dt className="text-slate-500">Elapsed</dt>
          <dd className="mt-1 font-mono text-slate-100">
            {formatElapsed(liveCall.elapsedSeconds)}
          </dd>
        </div>
        <div className="rounded-xl bg-slate-950/70 p-3">
          <dt className="text-slate-500">Frames</dt>
          <dd className="mt-1 font-mono text-slate-100">
            {liveCall.framesReceived}
          </dd>
        </div>
        <div className="rounded-xl bg-slate-950/70 p-3">
          <dt className="text-slate-500">Received</dt>
          <dd className="mt-1 font-mono text-slate-100">
            {formatBytes(liveCall.bytesReceived)}
          </dd>
        </div>
      </dl>

      {liveCall.error && (
        <div className="mt-4">
          <ErrorMessage message={liveCall.error} />
        </div>
      )}

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <button
          className="min-h-11 rounded-xl bg-emerald-400 px-5 py-2.5 font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
          disabled={isStartingOrLive}
          onClick={() => void liveCall.start()}
          type="button"
        >
          Start Live Call
        </button>
        <button
          className="min-h-11 rounded-xl border border-rose-400/50 bg-rose-400/10 px-5 py-2.5 font-semibold text-rose-100 transition hover:bg-rose-400/20 disabled:cursor-not-allowed disabled:border-slate-700 disabled:bg-slate-800 disabled:text-slate-500"
          disabled={!canStop}
          onClick={() => void liveCall.stop()}
          type="button"
        >
          Stop Live Call
        </button>
      </div>
    </section>
  );
}

export default LiveCallPanel;
