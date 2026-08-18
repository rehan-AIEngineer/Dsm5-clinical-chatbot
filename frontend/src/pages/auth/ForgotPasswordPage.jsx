// pages/auth/ForgotPassword.jsx
import { useState } from "react";

function ForgotPasswordPage({ onRequestReset, onGoToLogin }) {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await onRequestReset(email);
      setSent(true);
    } catch (err) {
      setError(err.message || "Couldn't send the reset link. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-50">
      <aside className="hidden w-[42%] shrink-0 flex-col justify-between bg-slate-900 p-10 text-slate-200 md:flex">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-teal-600 text-xs font-semibold text-white">
            DR
          </div>
          <span className="text-sm font-semibold text-white">DSM-5-TR Clinical Assistant</span>
        </div>

        <div>
          <h1 className="max-w-md text-4xl font-semibold leading-tight text-white">
            Grounded, careful answers — every time someone needs them.
          </h1>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-slate-400">
            We'll help you get back into your account so your conversations
            are right where you left them.
          </p>
        </div>

        <p className="text-xs text-slate-500">
          This is an educational reference tool, not an emergency service.
        </p>
      </aside>

      <main className="flex flex-1 items-center justify-center px-6">
        <div className="w-full max-w-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-teal-600">
            Account recovery
          </p>
          <h2 className="mt-1 text-2xl font-semibold text-slate-900">Reset your password</h2>

          {sent ? (
            <div className="mt-6 rounded-lg border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-800">
              If an account exists for <span className="font-medium">{email}</span>,
              a reset link is on its way. Check your inbox.
            </div>
          ) : (
            <>
              <p className="mt-1 text-sm text-slate-500">
                Enter your email and we'll send you a link to reset it.
              </p>

              <form onSubmit={handleSubmit}>
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

                {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

                <button
                  type="submit"
                  disabled={loading}
                  className="mt-6 w-full rounded-lg bg-teal-600 py-2.5 text-sm font-medium text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  {loading ? "Sending link…" : "Send reset link"}
                </button>
              </form>
            </>
          )}

          <p className="mt-4 text-center text-sm text-slate-500">
            Remembered your password?{" "}
            <button
              type="button"
              onClick={onGoToLogin}
              className="font-medium text-teal-600 hover:text-teal-700"
            >
              Sign in
            </button>
          </p>
        </div>
      </main>
    </div>
  );
}

export default ForgotPasswordPage;