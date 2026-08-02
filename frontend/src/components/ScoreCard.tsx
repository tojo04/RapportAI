import type { ScoreResult } from '../types/analysis';

interface ScoreCardProps {
  score: ScoreResult;
}

const CATEGORY_STYLES: Record<ScoreResult['category'], string> = {
  Excellent: 'bg-emerald-400/15 text-emerald-200',
  Good: 'bg-sky-400/15 text-sky-200',
  'Needs Improvement': 'bg-amber-400/15 text-amber-200',
  Poor: 'bg-rose-400/15 text-rose-200',
};

function ScoreCard({ score }: ScoreCardProps) {
  return (
    <section
      aria-labelledby="overall-score-heading"
      className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6"
    >
      <p className="text-sm font-medium text-slate-400">Overall call quality</p>
      <h2 id="overall-score-heading" className="mt-3 flex items-baseline gap-2">
        <span
          aria-label={`${score.total} out of 100`}
          className="text-6xl font-bold tracking-tight text-white"
        >
          {score.total}
        </span>
        <span aria-hidden="true" className="text-xl text-slate-400">
          / 100
        </span>
      </h2>
      <p
        className={`mt-5 inline-flex rounded-full px-3 py-1 text-sm font-semibold ${CATEGORY_STYLES[score.category]}`}
      >
        {score.category}
      </p>
    </section>
  );
}

export default ScoreCard;
