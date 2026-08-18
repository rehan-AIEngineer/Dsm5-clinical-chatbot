// pages/auth/ResetPassword.jsx
import { useState } from "react";

function ResetPasswordPage({ isValidLink, onSetNewPassword, onGoToForgot }) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }

    setLoading(true);
    try {
      await onSetNewPassword(password);
    } catch (err) {
      setError(err.message || "Couldn't reset your password. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-50">
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
            Choose a new, strong password for your account.
          </p>
        </div>

        <p className="text-xs text-slate-500">
          This is an educational reference tool, not an emergency service.
        </p>
      </aside>

      <main className="flex flex-1 items-center justify-center px-6">
        <div className="w-full max-w-sm">
          {!isValidLink ? (
            <>
              <p className="text-xs font-medium uppercase tracking-wide text-red-500">
                Link expired
              </p>
              <h2 className="mt-1 text-2xl font-semibold text-slate-900">
                This reset link is invalid or missing
              </h2>
              <p className="mt-2 text-sm text-slate-500">
                Reset links expire after a while for your security. Request a
                new one to continue.
              </p>
              <button
                type="button"
                onClick={onGoToForgot}
                className="mt-6 w-full rounded-lg bg-teal-600 py-2.5 text-sm font-medium text-white transition hover:bg-teal-700"
              >
                Request a new link
              </button>
            </>
          ) : (
            <>
              <p className="text-xs font-medium uppercase tracking-wide text-teal-600">
                New password
              </p>
              <h2 className="mt-1 text-2xl font-semibold text-slate-900">Set a new password</h2>
              <p className="mt-1 text-sm text-slate-500">
                Choose a new, strong password for your account.
              </p>

              <form onSubmit={handleSubmit}>
                <label className="mt-6 block text-sm font-medium text-slate-700">
                  New password
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                  />
                </label>

                <label className="mt-4 block text-sm font-medium text-slate-700">
                  Confirm password
                  <input
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter your password"
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
                  />
                </label>

                {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

                <button
                  type="submit"
                  disabled={loading}
                  className="mt-6 w-full rounded-lg bg-teal-600 py-2.5 text-sm font-medium text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  {loading ? "Resetting…" : "Reset password"}
                </button>
              </form>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

export default ResetPasswordPage;