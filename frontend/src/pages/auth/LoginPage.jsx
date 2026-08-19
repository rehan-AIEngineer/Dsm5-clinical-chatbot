// pages/auth/Login.jsx
// Reuses the exact design tokens from Sidebar.jsx / Message.jsx so the
// auth screens read as the same product as the chat interface — not a
// separate template bolted on.

import { useState } from "react";

function LoginPage({ onSignIn, onGoToSignup, onGoToForgot, successMessage }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await onSignIn(email, password);
    } catch (err) {
      setError(err.message || "Couldn't sign in. Check your details and try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-50">
      {/* Left panel — same slate-900 surface as the chat sidebar */}
      <aside className="hidden w-[42%] shrink-0 flex-col justify-between bg-slate-900 p-10 text-slate-200 md:flex">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-teal-600 text-sm font-semibold text-white">
            🌿
          </div>
          <span className="text-sm font-semibold text-white">MindBridge Clinical Companion</span>
        </div>

        <div>
          <h1 className="max-w-md text-3xl font-semibold leading-tight text-white">
            Empathetic mental health guidance and personalized care support.
          </h1>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-slate-400">
            Sign in to pick up your previous conversations, or start a fresh
            one whenever you need it.
          </p>
        </div>

        <p className="text-xs text-slate-500">
          This is an educational reference tool, not an emergency service.
        </p>
      </aside>

      {/* Right panel — the form */}
      <main className="flex flex-1 items-center justify-center px-6">
        <form onSubmit={handleSubmit} className="w-full max-w-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-teal-600">
            Welcome back
          </p>
          <h2 className="mt-1 text-2xl font-semibold text-slate-900">Sign in</h2>
          <p className="mt-1 text-sm text-slate-500">
            Continue your conversations and saved history.
          </p>

          {successMessage && (
            <div className="mt-4 rounded-lg border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-800">
              {successMessage}
            </div>
          )}

          <label className="mt-6 block text-sm font-medium text-slate-700">
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
            />
          </label>

          <div className="mt-4 flex items-center justify-between">
            <label className="text-sm font-medium text-slate-700">Password</label>
            <button
              type="button"
              onClick={onGoToForgot}
              className="text-sm font-medium text-teal-600 hover:text-teal-700"
            >
              Forgot password?
            </button>
          </div>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
          />

          {error && (
            <p className="mt-3 text-sm text-red-600">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="mt-6 w-full rounded-lg bg-teal-600 py-2.5 text-sm font-medium text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>

          <p className="mt-4 text-center text-sm text-slate-500">
            Don't have an account?{" "}
            <button
              type="button"
              onClick={onGoToSignup}
              className="font-medium text-teal-600 hover:text-teal-700"
            >
              Create one
            </button>
          </p>
        </form>
      </main>
    </div>
  );
}

export default LoginPage;