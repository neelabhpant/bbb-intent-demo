import { AnimatePresence, motion } from "framer-motion";

// Presentation metadata for each deterministic action returned by the API.
const ACTION_META = {
  checkout_nudge: { title: "Nudge to checkout", tag: "Convert" },
  bundle_offer: { title: "Offer a bundle", tag: "Grow basket" },
  capture_email_discount: { title: "Capture the email", tag: "Acquire" },
  re_engage_popular: { title: "Re-engage", tag: "Recover" },
  loyalty_reminder: { title: "Loyalty reminder", tag: "Retain" },
};

export default function ActionCard({ action }) {
  if (!action) return null;
  const meta = ACTION_META[action.action] ?? { title: action.action, tag: "Action" };

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={action.action}
        className="action"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="action__head">
          <span className="action__label">Next best action</span>
          <span className="action__tag">{meta.tag}</span>
        </div>
        <h2 className="action__title">{meta.title}</h2>
        <p className="action__message">{action.message}</p>
        <code className="action__code">{action.action}</code>
      </motion.div>
    </AnimatePresence>
  );
}
