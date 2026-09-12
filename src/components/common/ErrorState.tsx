import { AlertTriangle } from "lucide-react";
import Button from "./Button";

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export default function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-critical/25 bg-surface p-12 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-critical/10 text-critical">
        <AlertTriangle size={18} />
      </div>
      <p className="max-w-sm text-sm text-ink-dim">{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
