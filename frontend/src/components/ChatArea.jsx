// components/ChatArea.jsx
// Production chat UI — crisis banner + messages + input
// Top-Right toggle button enables Zone C (Pipeline Debugger) on demand.
// Step-by-step live agent runner during execution + fresh question telemetry reset.

import { useRef, useEffect, useState } from "react";
import Message from "./Message";

export default function ChatArea({
  messages = [],
  loading = false,
  onSend,
  inputValue,
  setInputValue,
  error,
  chatTitle,
  debugData,
}) {
  const bottomRef = useRef(null);
  const [showDebug, setShowDebug] = useState(false);
  const [activeStep, setActiveStep] = useState(1);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Step-by-step live progress timer matched to realistic agent execution times
  useEffect(() => {
    if (!loading) {
      setActiveStep(1);
      return;
    }
    setActiveStep(1);
    // Agent 1: Guardrail (~2s)
    const t1 = setTimeout(() => setActiveStep(2), 2200);
    // Agent 2: Clinical & Grief Reasoning Engine + RAG (~20s)
    const t2 = setTimeout(() => setActiveStep(3), 22000);
    // Agent 3: Empathy & Persona Synthesizer (~18s)
    const t3 = setTimeout(() => setActiveStep(4), 40000);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [loading]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!inputValue.trim() || loading) return;
    onSend(inputValue.trim());
    setInputValue("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const visibleMessages = messages.filter((m) => m.role !== "system");

  return (
    <div style={{ flex: 1, display: "flex", width: "100%", height: "100%", overflow: "hidden" }}>
      {/* Main Chat Stream */}
      <div className="chat-area">
        {/* ── Crisis support banner — always visible ── */}
        {/* ── Safe Space Banner ── */}
        <div className="crisis-banner">
          <span className="crisis-banner-icon">🌿</span>
          <p className="crisis-banner-text">
            <strong>Welcome to your safe space:</strong> Share your thoughts, symptoms, or feelings freely — every conversation is private and non-judgmental.
          </p>
        </div>


        {/* ── Chat header with top-right Zone C toggle ── */}
        <div className="chat-header">
          <div style={{ maxWidth: "320px", minWidth: 0 }}>
            <h1 className="chat-title">
              {chatTitle && chatTitle !== "New chat" && chatTitle !== "New conversation"
                ? chatTitle
                : "Mental Health Support"}
            </h1>
            <span className="chat-subtitle">Confidential · Clinical</span>
          </div>

          <div style={{ flex: 1 }} />

          {/* Top-Right Zone C Toggle Button */}
          <button
            onClick={() => setShowDebug((prev) => !prev)}
            style={{
              padding: "6px 12px",
              fontSize: "12px",
              fontWeight: "500",
              borderRadius: "6px",
              border: showDebug ? "1px solid var(--green)" : "1px solid var(--cream-border)",
              background: showDebug ? "var(--green-light)" : "var(--white)",
              color: showDebug ? "var(--green)" : "var(--text-muted)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              transition: "all 0.15s ease",
            }}
            title="Toggle Developer Pipeline Debugger"
          >
            <span>🐞</span>
            <span>{showDebug ? "Hide Pipeline Insights" : "Pipeline Insights"}</span>
          </button>
        </div>

        {/* ── Messages ── */}
        {visibleMessages.length === 0 && !loading ? (
          <div className="chat-empty">
            <div className="chat-empty-icon">🌿</div>
            <h2 className="chat-empty-title">How can we support you today?</h2>
            <p className="chat-empty-body">
              This is a safe, confidential space. You can ask about symptoms you've noticed,
              seek guidance on psychiatric conditions, or simply share what's on your mind.
            </p>
            <p className="chat-empty-note">
              Use "Add context" in the sidebar to share background that helps us personalise your support.
            </p>
          </div>
        ) : (
          <div className="chat-messages">
            {visibleMessages.map((msg, idx) => (
              <Message key={idx} role={msg.role} content={msg.content} />
            ))}

            {loading && visibleMessages[visibleMessages.length - 1]?.content !== "" && (
              <Message role="assistant" content="" />
            )}

            {error && (
              <div className="inline-error">
                Something went wrong. Please try again, or refresh if the issue continues.
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        )}

        {/* ── Input area ── */}
        <div className="chat-input-area">
          <form className="chat-input-form" onSubmit={handleSubmit}>
            <textarea
              className="chat-input"
              rows={1}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message…"
              disabled={loading}
            />
            <button
              type="submit"
              className="btn-send"
              disabled={loading || !inputValue.trim()}
            >
              {loading ? "…" : "Send"}
            </button>
          </form>
          <p className="chat-disclaimer">
            This tool provides information and support — it is not a substitute for professional medical advice.
            In a crisis, please call a helpline immediately.
          </p>
        </div>
      </div>

      {/* ── Zone C: Pipeline Debugger Drawer (Toggleable from Top-Right) ── */}
      {showDebug && (
        <div
          style={{
            width: "360px",
            flexShrink: 0,
            background: "#1E293B",
            color: "#F8FAFC",
            borderLeft: "1px solid #334155",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              padding: "14px 16px",
              borderBottom: "1px solid #334155",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: "#0F172A",
            }}
          >
            <div style={{ flex: 1 }}>
              <h3 style={{ fontSize: "14px", fontWeight: "600", color: "#38BDF8" }}>
                🐞 Zone C: Pipeline Debugger
              </h3>
              <p style={{ fontSize: "11px", color: "#94A3B8" }}>4-Agent Live Telemetry</p>
            </div>
            {debugData?.metrics?.total_time_ms && (
              <span
                style={{
                  fontSize: "11px",
                  fontFamily: "monospace",
                  background: "rgba(56, 189, 248, 0.15)",
                  color: "#38BDF8",
                  padding: "2px 8px",
                  borderRadius: "12px",
                  border: "1px solid rgba(56, 189, 248, 0.3)",
                }}
              >
                ⚡ {debugData.metrics.total_time_ms} ms
              </span>
            )}
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: "16px", display: "flex", flexDirection: "column", gap: "14px" }}>

            {/* Live progressive pipeline step-by-step runner while executing */}
            {loading && (
              <div style={{ background: "#0F172A", border: "1px solid #38BDF8", borderRadius: "8px", padding: "14px", display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ fontSize: "12px", fontWeight: "600", color: "#38BDF8", display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ display: "inline-block", width: "8px", height: "8px", borderRadius: "50%", background: "#38BDF8", animation: "pulse 1s infinite" }} />
                  Pipeline Executing Step-by-Step...
                </div>

                {/* Step 1 */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", color: activeStep >= 1 ? "#4ADE80" : "#64748B" }}>
                  <span>🔍 AGENT 1: Intent & Safety Guardrail</span>
                  <span>{activeStep > 1 ? "✅ Complete" : activeStep === 1 ? "⏳ Evaluating Risk..." : "Waiting..."}</span>
                </div>

                {/* Step 2 */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", color: activeStep >= 2 ? "#38BDF8" : "#64748B" }}>
                  <span>🧠 AGENT 2: Clinical & Grief Reasoning Engine</span>
                  <span>{activeStep > 2 ? "✅ Complete" : activeStep === 2 ? "⏳ Reasoning & Vector RAG..." : "Waiting..."}</span>
                </div>

                {/* Step 3 */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", color: activeStep >= 3 ? "#C084FC" : "#64748B" }}>
                  <span>❤️ AGENT 3: Empathy & Persona Synthesizer</span>
                  <span>{activeStep > 3 ? "✅ Complete" : activeStep === 3 ? "⏳ Synthesizing Response..." : "Waiting..."}</span>
                </div>

                {/* Step 4 */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: "11px", color: activeStep >= 4 ? "#4ADE80" : "#64748B" }}>
                  <span>✅ AGENT 4: Safety & Compliance Auditor</span>
                  <span>{activeStep >= 4 ? "⏳ Auditing Safety & Compliance..." : "Waiting..."}</span>
                </div>
              </div>
            )}

            {!loading && !debugData ? (
              <div style={{ textAlign: "center", padding: "30px 10px", color: "#64748B" }}>
                <span style={{ fontSize: "24px", display: "block", marginBottom: "8px" }}>📊</span>
                <p style={{ fontSize: "12px" }}>Send a message to view live agent outputs.</p>
              </div>
            ) : !loading && debugData ? (
              <>
                {/* Agent 1 */}
                <div style={{ background: "#0F172A", border: "1px solid #334155", borderRadius: "8px", padding: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <strong style={{ fontSize: "12px", color: "#4ADE80" }}>🔍 AGENT 1: Intent & Safety Guardrail</strong>
                    <span style={{ fontSize: "10px", color: "#94A3B8", fontFamily: "monospace" }}>{debugData.metrics?.agent1_time_ms || 0} ms</span>
                  </div>
                  <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", margin: "4px 0" }}>
                    <span style={{ fontSize: "10px", background: "rgba(74, 222, 128, 0.15)", color: "#4ADE80", padding: "2px 6px", borderRadius: "4px" }}>
                      Category: {debugData.agent1?.category}
                    </span>
                    {debugData.agent1?.passive_risk_flag && (
                      <span style={{ fontSize: "10px", background: "rgba(251, 191, 36, 0.15)", color: "#FBBF24", padding: "2px 6px", borderRadius: "4px" }}>
                        ⚠️ Passive Risk
                      </span>
                    )}
                  </div>
                  {debugData.agent1?.reasoning && (
                    <p style={{ fontSize: "11px", color: "#94A3B8", marginTop: "4px", lineHeight: "1.4" }}>
                      {debugData.agent1.reasoning}
                    </p>
                  )}
                </div>

                {/* Agent 2 */}
                <div style={{ background: "#0F172A", border: "1px solid #334155", borderRadius: "8px", padding: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <strong style={{ fontSize: "12px", color: "#38BDF8" }}>🧠 AGENT 2: Clinical & Grief Reasoning Engine</strong>
                    <span style={{ fontSize: "10px", color: "#94A3B8", fontFamily: "monospace" }}>{debugData.metrics?.agent2_time_ms || 0} ms</span>
                  </div>
                  <pre style={{ fontSize: "10px", fontFamily: "monospace", color: "#7DD3FC", background: "#1E293B", padding: "8px", borderRadius: "4px", overflowX: "auto", maxHeight: "140px" }}>
                    {JSON.stringify(debugData.agent2, null, 2)}
                  </pre>
                </div>

                {/* Agent 3 */}
                <div style={{ background: "#0F172A", border: "1px solid #334155", borderRadius: "8px", padding: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <strong style={{ fontSize: "12px", color: "#C084FC" }}>❤️ AGENT 3: Empathy & Persona Synthesizer</strong>
                    <span style={{ fontSize: "10px", color: "#94A3B8", fontFamily: "monospace" }}>{debugData.metrics?.agent3_time_ms || 0} ms</span>
                  </div>
                  <div style={{ fontSize: "11px", color: "#CBD5E1", background: "#1E293B", padding: "8px", borderRadius: "4px", maxHeight: "100px", overflowY: "auto" }}>
                    {debugData.agent3_draft || "(No draft)"}
                  </div>
                </div>

                {/* Agent 4 */}
                <div style={{ background: "#0F172A", border: "1px solid #334155", borderRadius: "8px", padding: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <strong style={{ fontSize: "12px", color: "#4ADE80" }}>✅ AGENT 4: Safety & Compliance Auditor</strong>
                    <span style={{ fontSize: "10px", color: "#94A3B8", fontFamily: "monospace" }}>{debugData.metrics?.agent4_time_ms || 0} ms</span>
                  </div>
                  <div style={{ fontSize: "11px", color: "#86EFAC", background: "#1E293B", padding: "8px", borderRadius: "4px", maxHeight: "100px", overflowY: "auto" }}>
                    {debugData.agent4_final || "(No final response)"}
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
