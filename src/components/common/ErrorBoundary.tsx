import { AlertTriangle } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

// A crash anywhere in a routed page (e.g. a third-party chart library
// throwing under some data/browser condition) is a render error React
// itself only stops by unmounting up to the nearest boundary above it --
// with none in this app, that meant the ENTIRE app (sidebar included)
// going blank instead of just the one broken page. This scopes that
// failure to the page content only, keeps navigation usable, and never
// silently swallows the error -- it's logged to the console for
// debugging.
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Page crashed:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-critical/25 bg-surface p-12 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-critical/10 text-critical">
            <AlertTriangle size={18} />
          </div>
          <p className="text-sm font-semibold text-ink">This page failed to load.</p>
          <p className="max-w-sm text-sm text-ink-dim">{this.state.error.message}</p>
          <button
            onClick={() => window.location.reload()}
            className="rounded-lg bg-surface-3 px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-surface-3/80"
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
