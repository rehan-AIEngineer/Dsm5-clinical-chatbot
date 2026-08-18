import { useState, useEffect, useRef } from "react";
import { useAuth } from "../context/AuthContext";

function Sidebar({
  chats,
  activeChatId,
  onNewChat,
  onSelectChat,
  onRenameChat,
  onDeleteChat,
  loadingChats = false,
  isContextOpen = false,
  onToggleContext,
}) {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(null);
  const [editingChat, setEditingChat] = useState(null);
  const [editTitle, setEditTitle] = useState("");
  const sidebarRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (menuOpen && !e.target.closest(".sidebar-menu-wrapper")) {
        setMenuOpen(null);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, [menuOpen]);

  const handleDelete = (id, e) => {
    e.stopPropagation();
    if (!confirm("Remove this conversation?")) return;
    setMenuOpen(null);
    void onDeleteChat(id);
  };

  const handleRename = (id) => {
    const trimmed = editTitle.trim();
    if (!trimmed) {
      setEditingChat(null);
      return;
    }
    setEditingChat(null);
    setMenuOpen(null);
    void onRenameChat(id, trimmed);
  };

  const startRename = (chat, e) => {
    e.stopPropagation();
    setEditingChat(chat.id);
    setEditTitle(chat.title || "New conversation");
    setMenuOpen(null);
  };

  const handleLogout = () => {
    if (!confirm("Sign out of your account?")) return;
    logout();
  };

  const initials = (user?.name || user?.email || "?").slice(0, 2).toUpperCase();

  return (
    <aside className="sidebar">
      {/* Top: Logo + Buttons */}
      <div className="sidebar-top">
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark">🌿</div>
          <span className="sidebar-logo-text">Companion</span>
        </div>

        <div className="sidebar-actions">
          <button className="btn-new-chat" onClick={onNewChat}>
            <span style={{ fontSize: 16, lineHeight: 1 }}>+</span>
            New conversation
          </button>
          <button
            className={`btn-add-context${isContextOpen ? " active" : ""}`}
            onClick={onToggleContext}
          >
            <span style={{ fontSize: 13 }}>{isContextOpen ? "✕" : "⊞"}</span>
            {isContextOpen ? "Close context" : "Add context"}
          </button>
        </div>
      </div>

      {/* Chat History */}
      <p className="sidebar-section-label">Conversations</p>

      <div className="sidebar-chat-list">
        {loadingChats ? (
          <p style={{ padding: "8px 10px", fontSize: 13, color: "var(--text-faint)" }}>
            Loading…
          </p>
        ) : chats.length === 0 ? (
          <p style={{ padding: "8px 10px", fontSize: 13, color: "var(--text-faint)" }}>
            No conversations yet
          </p>
        ) : (
          <ul style={{ listStyle: "none" }}>
            {chats.map((chat) => (
              <li key={chat.id} className="sidebar-chat-item" style={{ position: "relative" }}>
                {editingChat === chat.id ? (
                  <input
                    className="sidebar-chat-edit-input"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onBlur={() => handleRename(chat.id)}
                    onKeyDown={(e) => e.key === "Enter" && handleRename(chat.id)}
                    autoFocus
                  />
                ) : (
                  <button
                    className={`sidebar-chat-btn${chat.id === activeChatId ? " active" : ""}`}
                    onClick={() => onSelectChat(chat.id)}
                    title={chat.title}
                  >
                    {chat.title || "New conversation"}
                  </button>
                )}

                {editingChat !== chat.id && (
                  <div className="sidebar-menu-wrapper" style={{ position: "relative" }}>
                    <button
                      className="sidebar-chat-menu-btn"
                      aria-label="Conversation options"
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuOpen(menuOpen === chat.id ? null : chat.id);
                      }}
                    >
                      ⋮
                    </button>
                    {menuOpen === chat.id && (
                      <div className="sidebar-dropdown">
                        <button onClick={(e) => startRename(chat, e)}>
                          <span>✏️</span>
                          <span>Rename</span>
                        </button>
                        <button className="danger" onClick={(e) => handleDelete(chat.id, e)}>
                          <span>🗑️</span>
                          <span>Delete</span>
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Account Footer */}
      <div className="sidebar-footer">
        <div className="user-avatar">{initials}</div>
        <div className="user-info">
          <p className="user-name">{user?.name || "Account"}</p>
          <p className="user-email">{user?.email}</p>
        </div>
        <button className="btn-logout" onClick={handleLogout}>
          Sign out
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;