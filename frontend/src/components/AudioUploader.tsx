import { useState, type ChangeEvent, type FormEvent } from 'react';

import ErrorMessage from './ErrorMessage';

interface AudioUploaderProps {
  selectedFile: File | null;
  isLoading: boolean;
  onFileSelect: (file: File | null) => void;
  onSubmit: () => void;
}

const ACCEPTED_EXTENSIONS = ['.mp3', '.wav'];

function hasAcceptedExtension(filename: string): boolean {
  const lowerCaseName = filename.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((extension) =>
    lowerCaseName.endsWith(extension),
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.ceil(bytes / 1024))} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function AudioUploader({
  selectedFile,
  isLoading,
  onFileSelect,
  onSubmit,
}: AudioUploaderProps) {
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;

    if (!file) {
      setValidationError(null);
      onFileSelect(null);
      return;
    }

    if (!hasAcceptedExtension(file.name)) {
      setValidationError('Please choose an MP3 or WAV audio file.');
      onFileSelect(null);
      event.target.value = '';
      return;
    }

    setValidationError(null);
    onFileSelect(file);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (selectedFile && !isLoading) {
      onSubmit();
    }
  }

  return (
    <form
      className="rounded-2xl border border-slate-700 bg-slate-950/60 p-5 sm:p-6"
      onSubmit={handleSubmit}
    >
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">
            Upload a sales call
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Choose an MP3 or WAV recording to analyze.
          </p>
        </div>

        <label
          className={`relative inline-flex min-h-11 items-center justify-center rounded-xl border px-5 py-2.5 text-sm font-semibold transition ${
            isLoading
              ? 'cursor-not-allowed border-slate-700 bg-slate-800 text-slate-500'
              : 'cursor-pointer border-sky-400/50 bg-sky-400/10 text-sky-200 hover:border-sky-300 hover:bg-sky-400/20'
          }`}
        >
          Choose audio file
          <input
            accept=".mp3,.wav,audio/mpeg,audio/wav"
            className="absolute inset-0 cursor-pointer rounded-xl opacity-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-300 disabled:cursor-not-allowed"
            disabled={isLoading}
            onChange={handleFileChange}
            type="file"
          />
        </label>
      </div>

      {selectedFile && (
        <div className="mt-5 flex items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900 px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-100">
              {selectedFile.name}
            </p>
            <p className="mt-0.5 text-xs text-slate-400">
              {formatFileSize(selectedFile.size)}
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-emerald-400/10 px-2.5 py-1 text-xs font-medium text-emerald-300">
            Ready
          </span>
        </div>
      )}

      {validationError && (
        <div className="mt-5">
          <ErrorMessage message={validationError} />
        </div>
      )}

      <button
        aria-busy={isLoading}
        className="mt-5 min-h-12 w-full rounded-xl bg-sky-400 px-5 py-3 font-semibold text-slate-950 transition hover:bg-sky-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
        disabled={!selectedFile || isLoading}
        type="submit"
      >
        {isLoading ? 'Analyzing call…' : 'Analyze Call'}
      </button>
    </form>
  );
}

export default AudioUploader;
