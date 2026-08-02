function App() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 py-16 text-slate-100">
      <section className="w-full max-w-3xl rounded-3xl border border-slate-800 bg-slate-900/80 p-8 shadow-2xl shadow-sky-950/30 sm:p-12">
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
        <div className="mt-10 rounded-2xl border border-dashed border-slate-700 bg-slate-950/60 p-6 text-sm text-slate-400">
          Audio upload and call analysis are coming in the next build steps.
        </div>
      </section>
    </main>
  );
}

export default App;
