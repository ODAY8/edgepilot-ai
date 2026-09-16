import { motion } from "framer-motion";
import { Activity, Loader2, Lock, Mail } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import Button from "@/components/common/Button";
import { useAuth } from "@/context/AuthContext";

type Mode = "login" | "signup";

export default function Login() {
  const { user, loading: authLoading, signIn, signUp } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmationMessage, setConfirmationMessage] = useState<string | null>(null);

  // Already signed in -- no reason to show the login form again.
  if (!authLoading && user) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setConfirmationMessage(null);

    if (!email || !password) {
      setError("Enter both an email and a password.");
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "login") {
        const result = await signIn(email, password);
        if (result.error) {
          setError(result.error);
          return;
        }
        navigate("/dashboard", { replace: true });
      } else {
        const result = await signUp(email, password);
        if (result.error) {
          setError(result.error);
          return;
        }
        if (result.needsEmailConfirmation) {
          setConfirmationMessage("Account created. Check your email to confirm your address before signing in.");
          setMode("login");
        } else {
          navigate("/dashboard", { replace: true });
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-svh items-center justify-center bg-base px-4">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,rgba(91,124,250,0.12),transparent_45%)]" />

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative w-full max-w-sm rounded-2xl border border-border bg-surface p-6 shadow-2xl sm:p-8"
      >
        <div className="flex flex-col items-center text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-linear-to-br from-accent to-accent-2 shadow-[0_0_20px_-4px_rgba(91,124,250,0.7)]">
            <Activity size={20} className="text-white" strokeWidth={2.5} />
          </div>
          <h1 className="mt-4 text-xl font-bold text-ink">
            {mode === "login" ? "Sign in to EdgePilot" : "Create your EdgePilot account"}
          </h1>
          <p className="mt-1 text-sm text-ink-dim">
            {mode === "login" ? "Access your edge intelligence dashboard." : "Get started with EdgePilot AI."}
          </p>
        </div>

        {confirmationMessage && (
          <div className="mt-5 rounded-lg border border-safe/30 bg-safe/10 px-3 py-2.5 text-sm text-safe">
            {confirmationMessage}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="email" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-faint">
              Email
            </label>
            <div className="relative">
              <Mail size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-10 pr-3 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              />
            </div>
          </div>

          <div>
            <label htmlFor="password" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-faint">
              Password
            </label>
            <div className="relative">
              <Lock size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
              <input
                id="password"
                type="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-lg border border-border bg-surface-2 py-2.5 pl-10 pr-3 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              />
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-critical/30 bg-critical/10 px-3 py-2.5 text-sm text-critical">
              {error}
            </div>
          )}

          <Button type="submit" disabled={submitting} className="w-full" icon={submitting ? <Loader2 size={16} className="animate-spin" /> : undefined}>
            {submitting ? "Please wait…" : mode === "login" ? "Sign In" : "Create Account"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-dim">
          {mode === "login" ? "Don't have an account?" : "Already have an account?"}{" "}
          <button
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "signup" : "login");
              setError(null);
              setConfirmationMessage(null);
            }}
            className="font-semibold text-accent hover:underline"
          >
            {mode === "login" ? "Create one" : "Sign in"}
          </button>
        </p>
      </motion.div>
    </div>
  );
}
