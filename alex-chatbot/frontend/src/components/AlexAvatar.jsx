// Avatar de Alex en SVG. mood: "idle" | "thinking" | "happy"
export default function AlexAvatar({ size = 48, mood = "idle" }) {
  return (
    <svg
      className={`alex-avatar alex-${mood}`}
      width={size}
      height={size}
      viewBox="0 0 100 100"
      role="img"
      aria-label="Alex, asistente de biblioteca"
    >
      <circle cx="50" cy="50" r="48" fill="#e8eefc" />
      {/* cuerpo / camisa */}
      <path d="M14 96c2-20 17-30 36-30s34 10 36 30z" fill="#3b5bdb" />
      <path d="M42 66l8 10 8-10z" fill="#fff" />
      {/* cuello y cabeza */}
      <rect x="44" y="56" width="12" height="12" rx="4" fill="#f1c9a5" />
      <ellipse cx="50" cy="42" rx="19" ry="21" fill="#f7d6b7" />
      {/* cabello */}
      <path d="M31 40c0-16 10-23 20-23s19 7 19 22c-4-8-10-11-19-11s-16 3-20 12z" fill="#4a3428" />
      {/* lentes */}
      <g fill="none" stroke="#2b2b2b" strokeWidth="2.2">
        <circle cx="42" cy="43" r="6.5" />
        <circle cx="58" cy="43" r="6.5" />
        <path d="M48.5 43h3" />
      </g>
      {/* ojos (parpadean) */}
      <g className="alex-eyes" fill="#2b2b2b">
        <ellipse cx="42" cy="43" rx="2" ry="2.4" />
        <ellipse cx="58" cy="43" rx="2" ry="2.4" />
      </g>
      {/* boca */}
      {mood === "thinking" ? (
        <circle cx="50" cy="57" r="2.4" fill="#b5654f" />
      ) : (
        <path d="M43 55q7 7 14 0" fill="none" stroke="#b5654f" strokeWidth="2.2" strokeLinecap="round" />
      )}
      {/* libro */}
      <g transform="translate(60 74) rotate(-8)">
        <rect width="22" height="16" rx="2" fill="#f59f00" />
        <rect x="2" y="2" width="18" height="12" rx="1" fill="#fff3bf" />
        <path d="M11 2v12" stroke="#f59f00" strokeWidth="1.2" />
      </g>
    </svg>
  );
}
