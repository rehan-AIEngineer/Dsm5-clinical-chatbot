// App.jsx
import { useEffect, useState, useRef } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import { createNewChat, sendMessage as sendMessageApi } from "./api/chatbotApi";

function makeTitle(text) {
  const trimmed = text.trim();
  return trimmed.length > 32 ? trimmed.slice(0, 32) + "…" : trimmed;
}

function App() {
  const [chats, setChats] = useState([]); // [{ id, title, messages: [] }]
  const [activeChatId, setActiveChatId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const hasInitialized = useRef(false);

  const activeChat = chats.find((c) => c.id === activeChatId) || null;

  // Start with one fresh chat when the app first loads
  useEffect(() => {
    if (hasInitialized.current) return;
    hasInitialized.current = true;
    handleNewChat();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleNewChat = async () => {
    try {
      setError(null);
      const { session_id } = await createNewChat();
      setChats((prev) => [
        { id: session_id, title: "New chat", messages: [] },
        ...prev,
      ]);
      setActiveChatId(session_id);
    } catch (err) {
      setError("Couldn't start a new chat. Is the backend running?");
    }
  };

  const handleSelectChat = (id) => {
    setActiveChatId(id);
  };

  const handleSend = async (text) => {
    if (!activeChatId) return;

    setError(null);

    // Optimistically add the user's message, and set the chat title if this
    // is the first message in the conversation.
    setChats((prev) =>
      prev.map((c) =>
        c.id === activeChatId
          ? {
              ...c,
              title: c.messages.length === 0 ? makeTitle(text) : c.title,
              messages: [...c.messages, { role: "user", content: text }],
            }
          : c
      )
    );

    setLoading(true);
    try {
      const { answer } = await sendMessageApi(activeChatId, text);
      setChats((prev) =>
        prev.map((c) =>
          c.id === activeChatId
            ? { ...c, messages: [...c.messages, { role: "assistant", content: answer }] }
            : c
        )
      );
    } catch (err) {
      setChats((prev) =>
        prev.map((c) =>
          c.id === activeChatId
            ? {
                ...c,
                messages: [
                  ...c.messages,
                  {
                    role: "assistant",
                    content:
                      "Sorry, something went wrong reaching the assistant. Please try again.",
                  },
                ],
              }
            : c
        )
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-50">
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
      />

      <main className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <h1 className="text-sm font-semibold text-slate-700">
            {activeChat?.title && activeChat.title !== "New chat"
              ? activeChat.title
              : "DSM-5-TR Clinical Assistant"}
          </h1>
          {error && <span className="text-xs text-red-500">{error}</span>}
        </header>

        {activeChat ? (
          <ChatWindow
            messages={activeChat.messages}
            loading={loading}
            onSend={handleSend}
          />
        ) : (
          <div className="flex flex-1 items-center justify-center text-sm text-slate-400">
            Starting a new chat…
          </div>
        )}
      </main>
    </div>
  );
}

export default App;