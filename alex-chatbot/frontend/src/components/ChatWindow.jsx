import { useEffect, useRef, useState } from "react";
import AlexAvatar from "./AlexAvatar.jsx";
import { sendChat } from "../api.js";

const GREETING = {
  role: "assistant",
  content: "¡Hola! Soy Alex, tu asistente de biblioteca. Puedo buscar títulos en el catálogo y decirte si hay ejemplares disponibles. ¿Qué buscas hoy?",
};

const SUGGESTIONS = [
  "Busca libros sobre inteligencia artificial",
  "¿Hay ejemplares disponibles de Cien años de soledad?",
  "Busca por ISBN 9780307474728",
];

export default function ChatWindow() {
  const [messages, setMessages] = useState([GREETING]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text) {
    const content = text.trim();
    if (!content || loading) return;
    // El saludo inicial es solo de UI: la API exige que el historial empiece con "user".
    const next = [...messages, { role: "user", content }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const { reply, tools_used } = await sendChat(next.slice(1));
      setMessages([...next, { role: "assistant", content: reply, tools: tools_used }]);
    } catch {
      setMessages([
        ...next,
        { role: "assistant", content: "Uy, no pude conectarme con el catálogo. Intenta de nuevo en un momento.", error: true },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat">
      <header className="chat-header">
        <AlexAvatar size={44} mood={loading ? "thinking" : "idle"} />
        <div>
          <strong>Alex</strong>
          <span className="status">{loading ? "Consultando el catálogo…" : "Asistente de biblioteca"}</span>
        </div>
      </header>

      <div className="chat-body" aria-live="polite">
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}${m.error ? " error" : ""}`}>
            {m.role === "assistant" && <AlexAvatar size={32} />}
            <div className="bubble">{m.content}</div>
          </div>
        ))}
        {loading && (
          <div className="msg assistant">
            <AlexAvatar size={32} mood="thinking" />
            <div className="bubble typing"><span /><span /><span /></div>
          </div>
        )}
        {messages.length === 1 && (
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Escribe tu pregunta…"
          maxLength={4000}
          disabled={loading}
          autoFocus
        />
        <button type="submit" disabled={loading || !input.trim()}>Enviar</button>
      </form>
    </div>
  );
}
