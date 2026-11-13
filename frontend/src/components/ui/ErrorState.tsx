import { Button } from "./Button";

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ title = "Unable to reach the API", message, onRetry }: ErrorStateProps) {
  return (
    <div role="alert" className="rounded-2xl border border-rose-400/20 bg-rose-400/5 px-5 py-8">
      <h2 className="text-base font-semibold text-rose-100">{title}</h2>
      <p className="mt-2 max-w-xl text-sm leading-6 text-rose-100/80">{message}</p>
      {onRetry ? (
        <div className="mt-4">
          <Button onClick={onRetry}>Try again</Button>
        </div>
      ) : null}
    </div>
  );
}
