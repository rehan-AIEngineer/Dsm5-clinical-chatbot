// api/chatbotApi.js  

// FOR PRODUCTION, UNCOMMENT THE FOLLOWING LINE AND SET THE API BASE URL
// const API_BASE_URL = "https://dsm5-rag-chatbot-production.up.railway.app";

const API_BASE_URL = "http://localhost:8000"; // FOR LOCAL DEVELOPMENT

export async function createNewChat() {
  const res = await fetch(`${API_BASE_URL}/new-chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) throw new Error("Failed to create a new chat session.");

  return res.json();
}

export async function sendMessage(sessionId, message) {
  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      message,
    }),
  });

  if (!res.ok)
    throw new Error("Failed to get a response from the assistant.");

  return res.json();
}