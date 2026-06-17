import { useEffect } from "react";
import { animate, motion, useMotionValue, useTransform } from "framer-motion";

// The gauge sweeps 270 degrees (three quarters of the circle), with the gap at the
// bottom. pathLength is normalized to 1 so the dash math reads as fractions.
const ARC = 0.75;
const EASE = [0.16, 1, 0.3, 1];

function band(score) {
  if (score >= 0.6) return { label: "High intent", key: "high" };
  if (score >= 0.3) return { label: "Building", key: "mid" };
  return { label: "Low intent", key: "low" };
}

export default function IntentGauge({ score, loading }) {
  const target = score ?? 0;
  const meta = band(target);
  const dash = ARC * target;

  const count = useMotionValue(0);
  const display = useTransform(count, (value) => Math.round(value));

  useEffect(() => {
    const controls = animate(count, Math.round(target * 100), { duration: 1.1, ease: EASE });
    return () => controls.stop();
  }, [target, count]);

  return (
    <div className={`gauge ${loading ? "is-loading" : ""}`}>
      <svg viewBox="0 0 200 200" className="gauge__svg" aria-hidden="true">
        <defs>
          <linearGradient id="intentGrad" x1="0" y1="1" x2="1" y2="0">
            <stop offset="0%" stopColor="#46b3a3" />
            <stop offset="52%" stopColor="#e8a33d" />
            <stop offset="100%" stopColor="#e0584a" />
          </linearGradient>
        </defs>
        <g transform="rotate(135 100 100)">
          <circle
            className="gauge__track"
            cx="100"
            cy="100"
            r="84"
            pathLength="1"
            strokeDasharray={`${ARC} ${1 - ARC}`}
          />
          <motion.circle
            className="gauge__value"
            cx="100"
            cy="100"
            r="84"
            pathLength="1"
            stroke="url(#intentGrad)"
            strokeLinecap="round"
            initial={{ strokeDasharray: `0 1` }}
            animate={{ strokeDasharray: `${dash} ${1 - dash}` }}
            transition={{ duration: 1.1, ease: EASE }}
          />
        </g>
      </svg>

      <div className="gauge__center">
        <div className={`gauge__num tier-${meta.key}`}>
          <motion.span>{display}</motion.span>
          <span className="gauge__pct">%</span>
        </div>
        <div className="gauge__band">{loading ? "Scoring" : meta.label}</div>
        <div className="gauge__caption">purchase intent</div>
      </div>
    </div>
  );
}
