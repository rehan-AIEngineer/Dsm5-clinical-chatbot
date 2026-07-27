// api/chatbotApi.js
// Single place to change the backend URL and API calls.

const API_BASE_URL = "http://127.0.0.1:8000"; // <-- change this if your FastAPI runs elsewhere

export async function createNewChat() {
  const res = await fetch(`${API_BASE_URL}/new-chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error("Failed to create a new chat session.");
  return res.json(); // { session_id }
}

export async function sendMessage(sessionId, message) {
  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!res.ok) throw new Error("Failed to get a response from the assistant.");
  return res.json(); // { answer }
}