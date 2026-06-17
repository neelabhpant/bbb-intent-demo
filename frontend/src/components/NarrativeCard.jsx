import { AnimatePresence, motion } from "framer-motion";

// Plain-language read of the score, generated server-side from the model's own
// numbers. Hidden entirely when no model endpoint is configured or a request fails.
export default function NarrativeCard({ narrative, loading }) {
  if (!loading && !narrative) return null;

  return (
    <section className="narrative" aria-live="polite">
      <span className="narrative__head">Analyst read</span>
      <AnimatePresence mode="wait">
        {narrative ? (
          <motion.p
            key={narrative}
            className="narrative__text"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          >
            {narrative}
          </motion.p>
        ) : (
          <motion.div
            key="shimmer"
            className="narrative__shimmer"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            aria-hidden="true"
          >
            <span style={{ width: "92%" }} />
            <span style={{ width: "98%" }} />
            <span style={{ width: "61%" }} />
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
