// App.jsx — Production layout: Sidebar + ContextPanel (collapsible) + ChatArea
// Context state lifted here; Zone C accessible via top-right toggle on ChatArea.
import "./App.css";
import { useEffect, useState, useRef } from "react";
import Sidebar from "./components/Sidebar";
import ContextPanel from "./components/ContextPanel";
import ChatArea from "./components/ChatArea";
import { useAuth } from "./context/AuthContext";
import LoginPage from "./pages/auth/LoginPage";
import SignupPage from "./pages/auth/SignupPage";
import ForgotPasswordPage from "./pages/auth/ForgotPasswordPage";
import ResetPasswordPage from "./pages/auth/ResetPasswordPage";
import {
  createNewChat,
  deleteChat,
  renameChat,
  sendPipelineMessage,
  getChats,
  getChatById,
  linkGriefEntrySession,
} from "./api/chatbotApi";


const FALLBACK_ANSWER =
  "I'm having trouble responding right now. Please try again in a moment.";

function makeTitle(text) {
  const t = text.trim();
  return t.length > 40 ? t.slice(0, 40) + "…" : t;
}


function App() {
  const {
    session,
    isAuthenticated,
    checkingAuth,
    isRecovery,
    login,
    signup,
    forgotPassword,
    resetPassword,
  } = useAuth();

  // ── Auth view ──
  const [authView, setAuthView] = useState("login");

  // ── Chat / session state ──
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [loadingChats, setLoadingChats] = useState(true);
  const [loadingChatId, setLoadingChatId] = useState(null);
  const [chatInput, setChatInput] = useState("");

  // ── Zone C Debug Data state ──
  const [debugData, setDebugData] = useState(null);

  // ── Context panel visibility ──
  const [showContext, setShowContext] = useState(false);

  // ── Clinical context state (lifted from ContextPanel) ──
  const [featureMode, setFeatureMode] = useState("clinical_support");
  const [userRole, setUserRole] = useState("caregiver");
  const [diagnosisStatus, setDiagnosisStatus] = useState("unknown");
  const [reportedSymptoms, setReportedSymptoms] = useState("");
  const [durationMonths, setDurationMonths] = useState("");
  const [substanceUse, setSubstanceUse] = useState("");
  const [relationship, setRelationship] = useState("");
  // Grief state
  const [lossRelationship, setLossRelationship] = useState("");
  const [timeSinceLoss, setTimeSinceLoss] = useState("6_months");
  const [griefThemes, setGriefThemes] = useState("");
  // Calendar
  const [selectedDate, setSelectedDate] = useState(
    () => new Date().toISOString().split("T")[0]
  );
  const [calendarText, setCalendarText] = useState("");

  const hasInitialized = useRef(false);
  const loadingChatIdsRef = useRef(new Set());
  const activeUserIdRef = useRef(null);

  const activeChat = chats.find((c) => c.id === activeChatId) || null;
  const isActiveChatLoading =
    !!activeChatId &&
    !!loadingChatId &&
    loadingChatId === activeChatId &&
    (!activeChat || activeChat.messages.length === 0);

  // ── Reset on user switch ──
  useEffect(() => {
    const nextUserId = session?.user?.id ?? null;
    if (activeUserIdRef.current === nextUserId) return;
    activeUserIdRef.current = nextUserId;
    hasInitialized.current = false;
    loadingChatIdsRef.current.clear();
    setChats([]);
    setActiveChatId(null);
    setLoading(false);
    setError(null);
    setLoadingChats(!!nextUserId);
    setLoadingChatId(null);
    setDebugData(null);
  }, [session?.user?.id]);

  // ── Load messages for a chat from DB ──
  const loadChatMessages = async (chatId) => {
    if (!chatId || loadingChatIdsRef.current.has(chatId)) return;
    loadingChatIdsRef.current.add(chatId);
    setLoadingChatId(chatId);
    try {
      const data = await getChatById(chatId);
      if (data.messages) {
        setChats((prev) =>
          prev.map((c) =>
            c.id === chatId ? { ...c, messages: data.messages } : c
          )
        );
      }
    } finally {
      loadingChatIdsRef.current.delete(chatId);
      setLoadingChatId((cur) => (cur === chatId ? null : cur));
    }
  };

  // ── Promote temp chat to DB session ──
  const createPersistentChat = async (temporaryId) => {
    const { session_id } = await createNewChat();
    setChats((prev) =>
      prev.map((c) =>
        c.id === temporaryId ? { ...c, id: session_id, persisted: true } : c
      )
    );
    setActiveChatId((cur) => (cur === temporaryId ? session_id : cur));
    return session_id;
  };

  const handleChatUpdate = async () => {
    try {
      const data = await getChats();
      if (data.sessions) {
        setChats((prev) => {
          const serverIds = new Set(data.sessions.map((s) => s.session_id));
          const serverChats = data.sessions.map((s) => {
            const existing = prev.find((c) => c.id === s.session_id);
            return {
              id: s.session_id,
              title: s.title || "New conversation",
              messages: existing?.messages || [],
              created_at: s.created_at,
              persisted: true,
            };
          });
          const optimisticChats = prev.filter(
            (c) => c.pendingCreate && !serverIds.has(c.id)
          );
          return [...optimisticChats, ...serverChats];
        });
      }
    } catch {
      setError("Couldn't refresh conversations.");
    }
  };

  const handleRenameChat = async (id, newTitle) => {
    const t = newTitle.trim();
    if (!t) return;
    setChats((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: t } : c))
    );
    try {
      await renameChat(id, t);
    } catch {
      await handleChatUpdate();
    }
  };

  const handleDeleteChat = async (id) => {
    const next = chats.filter((c) => c.id !== id);
    setChats(next);
    if (activeChatId === id) setActiveChatId(next[0]?.id ?? null);
    try {
      await deleteChat(id);
    } catch {
      await handleChatUpdate();
    }
  };

  // ── Initial load ──
  useEffect(() => {
    if (!isAuthenticated || hasInitialized.current) return;
    hasInitialized.current = true;

    const loadChats = async () => {
      try {
        setLoadingChats(true);
        setError(null);
        const data = await getChats();
        if (data.sessions?.length > 0) {
          const loaded = data.sessions.map((s) => ({
            id: s.session_id,
            title: s.title || "New conversation",
            messages: [],
            created_at: s.created_at,
            persisted: true,
          }));
          setChats(loaded);
          setActiveChatId(loaded[0].id);
          void Promise.allSettled(loaded.map((c) => loadChatMessages(c.id)));
        } else {
          await handleNewChat();
        }
      } catch {
        setError("Couldn't load conversations. Is the backend running?");
        await handleNewChat();
      } finally {
        setLoadingChats(false);
      }
    };

    loadChats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  // ── Load messages when switching chat ──
  useEffect(() => {
    if (!isAuthenticated || loadingChats || !activeChatId) return;
    const active = chats.find((c) => c.id === activeChatId);
    if (!active || active.messages.length > 0 || active.pendingCreate) return;
    setError(null);
    void loadChatMessages(activeChatId).catch(() =>
      setError("Couldn't load conversation history.")
    );
  }, [activeChatId, chats, isAuthenticated, loadingChats]);

  const handleSelectChat = (id) => {
    setActiveChatId(id);
    const existing = chats.find((c) => c.id === id);
    if (!existing || existing.messages.length === 0) {
      setError(null);
      void loadChatMessages(id).catch(() =>
        setError("Couldn't load conversation history.")
      );
    }
  };

  const handleNewChat = async () => {
    const emptyChat = chats.find(
      (c) => c.messages.length === 0 && c.title === "New conversation"
    );
    if (emptyChat) {
      setActiveChatId(emptyChat.id);
      return;
    }
    const tempId = `temp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    setChats((prev) => [
      { id: tempId, title: "New conversation", messages: [], persisted: false },
      ...prev,
    ]);
    setActiveChatId(tempId);
    setDebugData(null);
  };

  // ── Build session context from lifted state ──
  const buildSessionContext = () => {
    if (featureMode === "grief_workbook") {
      return {
        feature_mode: "grief_workbook",
        user_role: "grieving",
        grief_data: {
          user_memory_profile: {
            deceased_or_loss: lossRelationship || undefined,
            time_since_loss: timeSinceLoss,
            grief_themes: griefThemes
              ? griefThemes.split(",").map((s) => s.trim()).filter(Boolean)
              : [],
          },
          current_workbook_entry:
            calendarText
              ? { entry_date: selectedDate, entry_text: calendarText }
              : null,
        },
      };
    }
    // clinical_support (or empty — all fields optional)
    const ctx = { feature_mode: "clinical_support" };
    if (userRole) ctx.user_role = userRole;
    if (diagnosisStatus) ctx.diagnosis_status = diagnosisStatus;
    const clinical = {};
    if (relationship) clinical.relationship = relationship;
    if (reportedSymptoms)
      clinical.reported_symptoms = reportedSymptoms
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    if (durationMonths) clinical.duration_months = durationMonths;
    if (substanceUse) clinical.substance_use = substanceUse;
    if (Object.keys(clinical).length > 0) ctx.clinical_data = clinical;
    return ctx;
  };

  // ── Unified send: 4-agent pipeline + PostgreSQL session save ──
  const handleSend = async (text) => {
    if (!activeChatId || !text.trim()) return;
    setError(null);

    const isTemp =
      activeChat?.id?.startsWith("temp-") || !activeChat?.persisted;

    // Optimistic UI
    setChats((prev) =>
      prev.map((c) =>
        c.id === activeChatId
          ? {
            ...c,
            title: c.messages.length === 0 ? makeTitle(text) : c.title,
            messages: [
              ...c.messages,
              { role: "user", content: text },
              { role: "assistant", content: "" },
            ],
          }
          : c
      )
    );

    setLoading(true);
    setDebugData(null); // Clear previous question's debug telemetry immediately
    let chatId = activeChatId;

    try {
      if (isTemp) chatId = await createPersistentChat(activeChatId);

      const ctx = buildSessionContext();
      const res = await sendPipelineMessage(chatId, text, ctx);
      const answer = res.answer || FALLBACK_ANSWER;

      if (res.debug) {
        setDebugData(res.debug);
      }

      // Smooth streaming typing effect
      let currentLen = 0;
      const chunkSize = 3;
      const interval = setInterval(() => {
        currentLen += chunkSize;
        const currentText = answer.slice(0, currentLen);

        setChats((prev) =>
          prev.map((c) => {
            if (c.id !== chatId) return c;
            const msgs = [...c.messages];
            const last = msgs.length - 1;
            if (last >= 0 && msgs[last].role === "assistant") {
              msgs[last] = { role: "assistant", content: currentText };
            }
            return { ...c, messages: msgs };
          })
        );

        if (currentLen >= answer.length) {
          clearInterval(interval);
        }
      }, 15);
    } catch (err) {
      setChats((prev) =>
        prev.map((c) => {
          if (c.id !== chatId) return c;
          const msgs = [...c.messages];
          const last = msgs.length - 1;
          if (last >= 0 && msgs[last].role === "assistant") {
            msgs[last] = { role: "assistant", content: FALLBACK_ANSWER };
          }
          return { ...c, messages: msgs };
        })
      );
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  // ── Open or continue conversation from a Grief Calendar reflection ──
  const handleOpenReflectionChat = async (date, text, existingSessionId = null, entryId = null) => {
    if (!text || !text.trim()) return;

    // If an existing conversation is already linked and loaded, switch to it!
    if (existingSessionId && chats.some((c) => c.id === existingSessionId)) {
      handleSelectChat(existingSessionId);
      return;
    }

    // Otherwise, create a NEW conversation with this reflection as the initial prompt
    try {
      setLoading(true);
      setError(null);

      // 1. Create a new persistent chat on the backend
      const { session_id } = await createNewChat();
      const reflectionText = text.trim();
      const chatTitle = reflectionText.length > 32 ? reflectionText.slice(0, 32) + "…" : reflectionText;

      const newChatObj = {
        id: session_id,
        title: chatTitle,
        messages: [
          { role: "user", content: reflectionText },
          { role: "assistant", content: "" },
        ],
        created_at: new Date().toISOString(),
        persisted: true,
      };

      setChats((prev) => [newChatObj, ...prev]);
      setActiveChatId(session_id);

      // 2. Link this new session_id to the grief reflection in DB
      try {
        await linkGriefEntrySession(date, session_id, entryId);
      } catch (e) {
        console.warn("Could not link session to reflection:", e);
      }

      // 3. Send through 4-agent pipeline
      const ctx = {
        feature_mode: "grief_workbook",
        user_role: "grieving",
        grief_data: {
          user_memory_profile: {
            deceased_or_loss: lossRelationship || undefined,
            time_since_loss: timeSinceLoss,
            grief_themes: griefThemes
              ? griefThemes.split(",").map((s) => s.trim()).filter(Boolean)
              : [],
          },
          current_workbook_entry: { entry_date: date, entry_text: reflectionText },
        },
      };

      const res = await sendPipelineMessage(session_id, reflectionText, ctx);
      const answer = res.answer || FALLBACK_ANSWER;

      if (res.debug) {
        setDebugData(res.debug);
      }

      // Typing animation
      let currentLen = 0;
      const chunkSize = 3;
      const interval = setInterval(() => {
        currentLen += chunkSize;
        const currentText = answer.slice(0, currentLen);
        setChats((prev) =>
          prev.map((c) => {
            if (c.id !== session_id) return c;
            const msgs = [...c.messages];
            const last = msgs.length - 1;
            if (last >= 0 && msgs[last].role === "assistant") {
              msgs[last] = { role: "assistant", content: currentText };
            }
            return { ...c, messages: msgs };
          })
        );
        if (currentLen >= answer.length) {
          clearInterval(interval);
        }
      }, 15);
    } catch (err) {
      setError(err.message || "Failed to open conversation from reflection.");
    } finally {
      setLoading(false);
    }
  };

  // ── Auth gating ──
  if (checkingAuth) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
        <p style={{ fontSize: 14, color: "var(--text-muted)" }}>Loading…</p>
      </div>
    );
  }

  if (isRecovery)
    return (
      <ResetPasswordPage
        isValidLink
        onSetNewPassword={resetPassword}
        onGoToForgot={() => setAuthView("forgot")}
      />
    );

  if (!isAuthenticated) {
    if (authView === "signup")
      return (
        <SignupPage
          onSignUp={signup}
          onGoToLogin={() => setAuthView("login")}
        />
      );
    if (authView === "forgot")
      return (
        <ForgotPasswordPage
          onRequestReset={forgotPassword}
          onGoToLogin={() => setAuthView("login")}
        />
      );
    return (
      <LoginPage
        onSignIn={login}
        onGoToSignup={() => setAuthView("signup")}
        onGoToForgot={() => setAuthView("forgot")}
      />
    );
  }

  // ── Authenticated: Production layout ──
  return (
    <div className="app-shell">
      {/* Left: Session history sidebar */}
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
        onChatUpdate={handleChatUpdate}
        onRenameChat={handleRenameChat}
        onDeleteChat={handleDeleteChat}
        loadingChats={loadingChats}
        isContextOpen={showContext}
        onToggleContext={() => setShowContext((v) => !v)}
      />

      {/* Middle: Collapsible context panel */}
      <ContextPanel
        isOpen={showContext}
        onClose={() => setShowContext(false)}
        sessionId={activeChatId}
        featureMode={featureMode} setFeatureMode={setFeatureMode}
        userRole={userRole} setUserRole={setUserRole}
        diagnosisStatus={diagnosisStatus} setDiagnosisStatus={setDiagnosisStatus}
        reportedSymptoms={reportedSymptoms} setReportedSymptoms={setReportedSymptoms}
        durationMonths={durationMonths} setDurationMonths={setDurationMonths}
        substanceUse={substanceUse} setSubstanceUse={setSubstanceUse}
        relationship={relationship} setRelationship={setRelationship}
        lossRelationship={lossRelationship} setLossRelationship={setLossRelationship}
        timeSinceLoss={timeSinceLoss} setTimeSinceLoss={setTimeSinceLoss}
        griefThemes={griefThemes} setGriefThemes={setGriefThemes}
        calendarText={calendarText} setCalendarText={setCalendarText}
        selectedDate={selectedDate} setSelectedDate={setSelectedDate}
        onOpenReflectionChat={handleOpenReflectionChat}
        onSelectChat={handleSelectChat}
      />

      {/* Right: Main chat with top-right Zone C debug toggle */}
      <ChatArea
        messages={activeChat?.messages || []}
        loading={loading || isActiveChatLoading}
        onSend={handleSend}
        inputValue={chatInput}
        setInputValue={setChatInput}
        error={error}
        chatTitle={activeChat?.title}
        debugData={debugData}
      />
    </div>
  );
}

export default App;