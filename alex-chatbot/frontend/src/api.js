export async function sendChat(messages) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages: messages.map(({ role, content }) => ({ role, content })) }),
  });
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json(); // { reply, tools_used }
}
