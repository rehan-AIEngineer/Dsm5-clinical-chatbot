// pages/auth/Signup.jsx
import { useState } from "react";

function SignupPage({ onSignUp, onGoToLogin, onSignUpSuccess }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await onSignUp(name, email, password);
      if (onSignUpSuccess) {
        onSignUpSuccess("Account created successfully! Please sign in with your email and password.");
      } else if (onGoToLogin) {
        onGoToLogin();
      }
    } catch (err) {
      setError(err.message || "Couldn't create your account. Please try again.");
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
            Create an account to save your conversations and pick up right
            where you left off.
          </p>
        </div>

        <p className="text-xs text-slate-500">
          This is an educational reference tool, not an emergency service.
        </p>
      </aside>

      <main className="flex flex-1 items-center justify-center px-6">
        <form onSubmit={handleSubmit} className="w-full max-w-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-teal-600">
            Get started
          </p>
          <h2 className="mt-1 text-2xl font-semibold text-slate-900">Create your account</h2>
          <p className="mt-1 text-sm text-slate-500">
            Takes less than a minute.
          </p>

          <label className="mt-6 block text-sm font-medium text-slate-700">
            Name
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-1 focus:ring-teal-500"
            />
          </label>

          <label className="mt-4 block text-sm font-medium text-slate-700">
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

          <label className="mt-4 block text-sm font-medium text-slate-700">
            Password
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

          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="mt-6 w-full rounded-lg bg-teal-600 py-2.5 text-sm font-medium text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {loading ? "Creating account…" : "Create account"}
          </button>

          <p className="mt-4 text-center text-sm text-slate-500">
            Already have an account?{" "}
            <button
              type="button"
              onClick={onGoToLogin}
              className="font-medium text-teal-600 hover:text-teal-700"
            >
              Sign in
            </button>
          </p>
        </form>
      </main>
    </div>
  );
}

export default SignupPage;