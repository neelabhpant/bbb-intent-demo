import { motion } from "framer-motion";

export default function SessionPicker({ sessions, selectedId, onSelect, disabled }) {
  return (
    <nav className="rail" aria-label="Demo sessions">
      <div className="rail__head">
        <span className="rail__eyebrow">Clickstream</span>
        <h2 className="rail__title">Sessions</h2>
      </div>
      <ul className="rail__list">
        {sessions.map((session, index) => {
          const active = session.session_id === selectedId;
          return (
            <li key={session.session_id}>
              <motion.button
                type="button"
                className={`session ${active ? "is-active" : ""}`}
                onClick={() => onSelect(session)}
                disabled={disabled}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.05 * index + 0.2, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              >
                <span className="session__id">{session.session_id}</span>
                <span className="session__label">{session.label}</span>
                {active && <span className="session__marker" aria-hidden="true" />}
              </motion.button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
