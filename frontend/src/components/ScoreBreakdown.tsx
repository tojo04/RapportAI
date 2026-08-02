import type { ScoreBreakdown as ScoreBreakdownData } from '../types/analysis';

interface ScoreBreakdownProps {
  breakdown: ScoreBreakdownData;
}

interface BreakdownItem {
  label: string;
  value: number;
  maximum: number;
}

function ScoreBreakdown({ breakdown }: ScoreBreakdownProps) {
  const items: BreakdownItem[] = [
    { label: 'Discovery', value: breakdown.discovery, maximum: 25 },
    {
      label: 'Objection handling',
      value: breakdown.objection_handling,
      maximum: 25,
    },
    {
      label: 'Communication clarity',
      value: breakdown.communication_clarity,
      maximum: 20,
    },
    {
      label: 'Confirmed next step',
      value: breakdown.confirmed_next_step,
      maximum: 20,
    },
    {
      label: 'Follow-up actions',
      value: breakdown.follow_up_actions,
      maximum: 10,
    },
  ];

  return (
    <section
      aria-labelledby="score-breakdown-heading"
      className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6"
    >
      <h2 id="score-breakdown-heading" className="text-lg font-semibold">
        Score breakdown
      </h2>
      <p className="mt-1 text-sm text-slate-400">
        Each component follows the deterministic scoring rules.
      </p>

      <dl className="mt-5 space-y-4">
        {items.map((item) => (
          <div key={item.label}>
            <div className="flex items-center justify-between gap-4 text-sm">
              <dt className="font-medium text-slate-200">{item.label}</dt>
              <dd className="text-slate-300">
                {item.value} / {item.maximum}
              </dd>
            </div>
            <div
              aria-label={`${item.label}: ${item.value} out of ${item.maximum}`}
              aria-valuemax={item.maximum}
              aria-valuemin={0}
              aria-valuenow={item.value}
              className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800"
              role="progressbar"
            >
              <div
                className="h-full rounded-full bg-sky-400"
                style={{ width: `${(item.value / item.maximum) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </dl>
    </section>
  );
}

export default ScoreBreakdown;
