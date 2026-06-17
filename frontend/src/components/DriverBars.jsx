import { motion } from "framer-motion";

// Diverging bars: a center line, contributions toward a purchase extend right (warm),
// contributions away extend left (teal). Bar length is scaled to the strongest driver.
export default function DriverBars({ drivers }) {
  if (!drivers || drivers.length === 0) return null;

  const max = Math.max(...drivers.map((d) => Math.abs(d.contribution))) || 1;

  return (
    <section className="drivers">
      <div className="drivers__head">
        <div>
          <span className="drivers__eyebrow">Explainability</span>
          <h2 className="drivers__title">Why this score</h2>
        </div>
        <div className="drivers__legend">
          <span className="legend legend--up"><i aria-hidden="true" /> toward buy</span>
          <span className="legend legend--down"><i aria-hidden="true" /> away</span>
        </div>
      </div>

      <p className="drivers__note">
        How each signal moved this session&rsquo;s intent &middot; the model&rsquo;s own
        feature contribution.
      </p>

      <ul className="drivers__list">
        {drivers.map((driver, index) => (
          <li className="driver" key={driver.label}>
            <div className="driver__meta">
              <span className="driver__label">{driver.label}</span>
              <span className="driver__value">{driver.value}</span>
            </div>
            <div className="driver__track">
              <motion.span
                className={`driver__bar driver__bar--${driver.direction}`}
                initial={{ width: 0 }}
                animate={{ width: `${(Math.abs(driver.contribution) / max) * 50}%` }}
                transition={{ duration: 0.8, delay: 0.05 * index, ease: [0.16, 1, 0.3, 1] }}
              />
            </div>
            <span className={`driver__amount tone-${driver.direction}`}>
              {driver.contribution > 0 ? "+" : ""}
              {driver.contribution.toFixed(2)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
