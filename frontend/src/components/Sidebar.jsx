// components/Sidebar.jsx

function Sidebar({ chats, activeChatId, onNewChat, onSelectChat }) {
  return (
    <aside className="flex h-full w-72 shrink-0 flex-col bg-slate-900 text-slate-200">
      <div className="p-4">
        <button
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-800 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-700"
        >
          <span className="text-lg leading-none">+</span>
          New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2">
        <p className="px-3 pb-2 pt-2 text-xs font-medium uppercase tracking-wide text-slate-500">
          Chats
        </p>

        {chats.length === 0 ? (
          <p className="px-3 text-sm text-slate-500">No conversations yet</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {chats.map((chat) => (
              <li key={chat.id}>
                <button
                  onClick={() => onSelectChat(chat.id)}
                  className={`w-full truncate rounded-lg px-3 py-2 text-left text-sm transition ${
                    chat.id === activeChatId
                      ? "bg-teal-600/20 text-teal-300"
                      : "text-slate-300 hover:bg-slate-800"
                  }`}
                  title={chat.title}
                >
                  {chat.title}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-slate-800 p-4 text-xs text-slate-500">
        Session data clears on refresh
      </div>
    </aside>
  );
}

export default Sidebar;