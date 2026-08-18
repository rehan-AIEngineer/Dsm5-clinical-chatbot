// pages/auth/AuthLayout.jsx
function AuthLayout({ eyebrow, title, subtitle, leftSubtitle, children }) {
  return (
    <div className="grid min-h-screen w-full grid-cols-1 bg-slate-50 md:grid-cols-2">
      <div className="hidden flex-col justify-between bg-slate-900 p-10 text-slate-200 md:flex">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-teal-600 text-xs font-semibold text-white">
            DR
          </span>
          DSM-5-TR Clinical Assistant
        </div>

        <div className="max-w-sm">
          <h1 className="text-2xl font-semibold leading-snug text-white">
            Grounded, careful answers — every time someone needs them.
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-slate-400">
            {leftSubtitle || "Sign in to pick up your previous conversations, or start a fresh one whenever you need it."}
          </p>
        </div>

        <p className="text-xs text-slate-500">
          This is an educational reference tool, not an emergency service.
        </p>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-sm">
          {eyebrow && (
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
              {eyebrow}
            </p>
          )}
          <h2 className="text-2xl font-semibold text-slate-800">{title}</h2>
          {subtitle && <p className="mt-2 text-sm text-slate-500">{subtitle}</p>}
          <div className="mt-6">{children}</div>
        </div>
      </div>
    </div>
  );
}

export default AuthLayout;