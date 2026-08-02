import type { CallAnalysis, Sentiment } from '../types/analysis';

interface AnalysisResultsProps {
  analysis: CallAnalysis;
  transcript: string;
}

interface ResultListProps {
  heading: string;
  items: string[];
}

const SENTIMENT_STYLES: Record<Sentiment, string> = {
  positive: 'bg-emerald-400/15 text-emerald-200',
  neutral: 'bg-slate-400/15 text-slate-200',
  mixed: 'bg-amber-400/15 text-amber-200',
  negative: 'bg-rose-400/15 text-rose-200',
};

function ResultList({ heading, items }: ResultListProps) {
  return (
    <section
      aria-labelledby={`${heading.toLowerCase().replaceAll(' ', '-')}-heading`}
    >
      <h3
        className="text-sm font-semibold uppercase tracking-wider text-slate-400"
        id={`${heading.toLowerCase().replaceAll(' ', '-')}-heading`}
      >
        {heading}
      </h3>
      {items.length > 0 ? (
        <ul className="mt-3 space-y-2 text-slate-200">
          {items.map((item, index) => (
            <li className="flex gap-3" key={`${item}-${index}`}>
              <span
                aria-hidden="true"
                className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400"
              />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm italic text-slate-500">None identified</p>
      )}
    </section>
  );
}

function AnalysisResults({ analysis, transcript }: AnalysisResultsProps) {
  return (
    <div className="space-y-6">
      <section
        aria-labelledby="call-summary-heading"
        className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6"
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 id="call-summary-heading" className="text-xl font-semibold">
              Call summary
            </h2>
            <p className="mt-3 leading-7 text-slate-300">{analysis.summary}</p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <span
              aria-label={`Sentiment: ${analysis.sentiment}`}
              className={`rounded-full px-3 py-1 text-sm font-semibold capitalize ${SENTIMENT_STYLES[analysis.sentiment]}`}
            >
              {analysis.sentiment}
            </span>
            <span className="rounded-full bg-sky-400/10 px-3 py-1 text-sm font-medium text-sky-200">
              Next step:{' '}
              {analysis.next_step_confirmed ? 'Confirmed' : 'Not confirmed'}
            </span>
          </div>
        </div>
      </section>

      <section
        aria-label="Structured call insights"
        className="grid gap-6 rounded-2xl border border-slate-700 bg-slate-900/80 p-6 md:grid-cols-2"
      >
        <ResultList heading="Customer needs" items={analysis.customer_needs} />
        <ResultList
          heading="Questions asked"
          items={analysis.questions_asked}
        />
        <ResultList
          heading="Follow-up actions"
          items={analysis.follow_up_actions}
        />

        <section aria-labelledby="objections-heading">
          <h3
            className="text-sm font-semibold uppercase tracking-wider text-slate-400"
            id="objections-heading"
          >
            Objections and responses
          </h3>
          {analysis.objections.length > 0 ? (
            <ul className="mt-3 space-y-3">
              {analysis.objections.map((item, index) => (
                <li
                  className="rounded-xl border border-slate-800 bg-slate-950/60 p-4"
                  key={`${item.objection}-${index}`}
                >
                  <p className="font-medium text-slate-100">{item.objection}</p>
                  <p className="mt-2 text-sm text-slate-400">
                    <span className="font-medium text-slate-300">
                      Response:{' '}
                    </span>
                    {item.response ?? 'No response provided'}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm italic text-slate-500">
              None identified
            </p>
          )}
        </section>
      </section>

      <details className="group rounded-2xl border border-slate-700 bg-slate-900/80 p-6">
        <summary className="cursor-pointer font-semibold text-slate-100 marker:text-sky-400">
          View transcript
        </summary>
        <p className="mt-5 whitespace-pre-wrap border-t border-slate-800 pt-5 leading-7 text-slate-300">
          {transcript}
        </p>
      </details>
    </div>
  );
}

export default AnalysisResults;
