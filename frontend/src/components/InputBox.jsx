// components/InputBox.jsx
import { useState } from "react";

function InputBox({ onSend, disabled }) {
  const [value, setValue] = useState("");

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-slate-200 bg-white px-4 py-4 sm:px-8">
      <div className="mx-auto flex max-w-3xl items-end gap-3 rounded-2xl border border-slate-300 bg-slate-50 px-4 py-2 shadow-sm focus-within:border-teal-500 focus-within:ring-1 focus-within:ring-teal-500">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about a diagnosis, symptom, or DSM-5-TR criteria…"
          rows={1}
          disabled={disabled}
          className="max-h-40 flex-1 resize-none bg-transparent py-2 text-[15px] text-slate-800 placeholder:text-slate-400 focus:outline-none disabled:opacity-60"
        />
        <button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className="mb-1 shrink-0 rounded-xl bg-teal-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          Send
        </button>
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-slate-400">
        Informational reference only — not a substitute for professional medical advice.
      </p>
    </div>
  );
}

export default InputBox;