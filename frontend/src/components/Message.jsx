// components/Message.jsx — Warm clinical chat bubbles
import ReactMarkdown from "react-markdown";

function Message({ role, content }) {
  const isUser = role === "user";
  const isLoading = !isUser && !content?.trim();

  if (isLoading) {
    return (
      <div className="msg-row assistant">
        <div className="msg-avatar assistant">🌿</div>
        <div className="msg-bubble assistant">
          <div className="typing-dots">
            <span /><span /><span />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`msg-row ${isUser ? "user" : "assistant"}`}>
      {!isUser && (
        <div className="msg-avatar assistant">🌿</div>
      )}

      <div className={`msg-bubble ${isUser ? "user" : "assistant"}`}>
        {isUser ? (
          <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{content}</p>
        ) : (
          <div className="prose">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        )}
      </div>

      {isUser && (
        <div className="msg-avatar user">You</div>
      )}
    </div>
  );
}

export default Message;