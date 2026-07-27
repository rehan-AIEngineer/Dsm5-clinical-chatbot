// components/Message.jsx
import ReactMarkdown from "react-markdown";

function Message({ role, content }) {
  const isUser = role === "user";

  return (
    <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`flex max-w-[75%] gap-3 ${
          isUser ? "flex-row-reverse" : "flex-row"
        }`}
      >
        {/* Avatar */}
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
            isUser
              ? "bg-slate-700 text-white"
              : "bg-teal-600 text-white"
          }`}
        >
          {isUser ? "You" : "DR"}
        </div>

        {/* Bubble */}
        <div
          className={`rounded-2xl px-4 py-3 text-[15px] leading-relaxed ${
            isUser
              ? "rounded-tr-sm bg-slate-800 text-white"
              : "rounded-tl-sm border border-slate-200 bg-white text-slate-800 shadow-sm"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{content}</p>
          ) : (
            <div className="prose prose-sm max-w-none prose-p:my-2 prose-headings:my-2 prose-ul:my-2 prose-li:my-0.5 prose-a:no-underline">
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Message;