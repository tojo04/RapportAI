interface ErrorMessageProps {
  message: string;
}

function ErrorMessage({ message }: ErrorMessageProps) {
  return (
    <div
      className="rounded-xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100"
      role="alert"
    >
      <p className="font-semibold">Something went wrong</p>
      <p className="mt-1 text-rose-200">{message}</p>
    </div>
  );
}

export default ErrorMessage;
