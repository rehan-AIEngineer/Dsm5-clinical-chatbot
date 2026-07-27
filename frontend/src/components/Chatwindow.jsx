// components/ChatWindow.jsx
import { useEffect, useRef } from "react";
import Message from "./Message";
import InputBox from "./InputBox";

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex max-w-[75%] gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-600 text-xs font-semibold text-white">
          DR
        </div>
        <div className="flex items-center gap-1 rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-teal-600 text-lg font-semibold text-white">
        DR
      </div>
      <h2 className="text-lg font-semibold text-slate-800">
        DSM-5-TR Clinical Reference Assistant
      </h2>
      <p className="mt-2 max-w-md text-sm text-slate-500">
        Ask about a diagnosis, its criteria, prevalence, risk factors, or how
        two conditions compare — answers are grounded in the DSM-5-TR.
      </p>
    </div>
  );
}

function ChatWindow({ messages, loading, onSend }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-8">
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-5">
            {messages.map((m, i) => (
              <Message key={i} role={m.role} content={m.content} />
            ))}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>
      <InputBox onSend={onSend} disabled={loading} />
    </div>
  );
}

export default ChatWindow;