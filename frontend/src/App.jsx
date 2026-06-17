import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import sessions from "./sample_sessions.json";
import { apiBaseUrl, isConfigured, narrateSession, scoreSession } from "./api.js";
import IntentGauge from "./components/IntentGauge.jsx";
import ActionCard from "./components/ActionCard.jsx";
import SessionPicker from "./components/SessionPicker.jsx";
import DriverBars from "./components/DriverBars.jsx";
import NarrativeCard from "./components/NarrativeCard.jsx";

const MONTHS = {
  Feb: "February", Mar: "March", May: "May", June: "June", Jul: "July",
  Aug: "August", Sep: "September", Oct: "October", Nov: "November", Dec: "December",
};

function visitorLabel(type) {
  return { Returning_Visitor: "Returning", New_Visitor: "New", Other: "Other" }[type] ?? type;
}

// Friendly labels for the raw and derived feature keys the model reports as drivers.
const FEATURE_LABELS = {
  Administrative: "Admin pages",
  Administrative_Duration: "Admin time",
  Informational: "Info pages",
  Informational_Duration: "Info time",
  ProductRelated: "Product pages",
  ProductRelated_Duration: "Product time",
  BounceRates: "Bounce rate",
  ExitRates: "Exit rate",
  SpecialDay: "Special day",
  Month: "Month",
  OperatingSystems: "Operating system",
  Browser: "Browser",
  Region: "Region",
  TrafficType: "Traffic type",
  VisitorType: "Visitor",
  Weekend: "Weekend",
  total_pages: "Total pages",
  total_duration: "Total time",
  avg_product_duration: "Avg product time",
};

function formatValue(feature, value) {
  if (feature === "Month") return MONTHS[value] ?? value;
  if (feature === "VisitorType") return visitorLabel(value);
  if (feature === "Weekend") return value ? "Yes" : "No";
  if (feature === "ExitRates" || feature === "BounceRates") return `${(value * 100).toFixed(1)}%`;
  if (feature.endsWith("_Duration") || feature === "total_duration" || feature === "avg_product_duration") {
    return `${Math.round(value)}s`;
  }
  return String(value);
}

function SignalStrip({ features }) {
  if (!features) return null;
  const items = [
    { k: "Product pages", v: features.ProductRelated },
    { k: "Product time", v: `${Math.round(features.ProductRelated_Duration)}s` },
    { k: "Exit rate", v: `${(features.ExitRates * 100).toFixed(1)}%` },
    { k: "Visitor", v: visitorLabel(features.VisitorType) },
    { k: "Month", v: MONTHS[features.Month] ?? features.Month },
    { k: "Weekend", v: features.Weekend ? "Yes" : "No" },
  ];
  return (
    <div className="signals">
      <span className="signals__head">Session signals</span>
      <dl className="signals__grid">
        {items.map((item) => (
          <div className="signals__cell" key={item.k}>
            <dt>{item.k}</dt>
            <dd>{item.v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default function App() {
  const configured = isConfigured();
  const [selected, setSelected] = useState(sessions[0]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [narrative, setNarrative] = useState(null);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [narrativeEnabled, setNarrativeEnabled] = useState(true);
  const narrateAbort = useRef(null);

  function runNarrative(session) {
    narrateAbort.current?.abort();
    const controller = new AbortController();
    narrateAbort.current = controller;
    setNarrative(null);
    setNarrativeLoading(true);
    narrateSession(session.features, { signal: controller.signal })
      .then((res) => {
        if (controller.signal.aborted) return;
        setNarrativeEnabled(res.enabled);
        setNarrative(res.narrative ?? null);
      })
      .catch(() => {
        // Aborted or unreachable: leave the card hidden.
      })
      .finally(() => {
        if (!controller.signal.aborted) setNarrativeLoading(false);
      });
  }

  async function run(session) {
    setSelected(session);
    setError(null);
    setLoading(true);
    runNarrative(session);
    try {
      const res = await scoreSession(session.features);
      setResult(res);
    } catch (err) {
      setResult(null);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (configured) run(sessions[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const drivers = (result?.drivers ?? []).map((d) => ({
    label: FEATURE_LABELS[d.feature] ?? d.feature,
    value: formatValue(d.feature, d.value),
    contribution: d.contribution,
    direction: d.direction,
  }));

  return (
    <div className="app">
      <div className="atmosphere" aria-hidden="true" />

      <header className="masthead">
        <motion.div
          className="masthead__brand"
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        >
          <span className="masthead__mark" aria-hidden="true" />
          <div>
            <h1 className="masthead__title">Purchase Intent</h1>
            <p className="masthead__sub">Session signal scoring &middot; next best action</p>
          </div>
        </motion.div>
        <div className="masthead__meta">
          <span className="dot" aria-hidden="true" />
          behavioral model
        </div>
      </header>

      {!configured && (
        <div className="banner">
          Set <code>VITE_API_BASE_URL</code> in <code>frontend/.env</code> to enable scoring.
        </div>
      )}

      <main className="stage">
        <SessionPicker
          sessions={sessions}
          selectedId={selected?.session_id}
          onSelect={run}
          disabled={loading || !configured}
        />

        <div className="content">
          <section className="board">
            <div className="board__gauge">
              <IntentGauge score={result?.intent_score} loading={loading} />
            </div>

            <div className="board__side">
              {error ? (
                <div className="error" role="alert">
                  {error}
                </div>
              ) : (
                <ActionCard action={result?.next_best_action} />
              )}
              <SignalStrip features={selected?.features} />
            </div>
          </section>

          {!error && (
            <NarrativeCard
              narrative={narrative}
              loading={narrativeLoading && narrativeEnabled}
            />
          )}
          {!error && <DriverBars drivers={drivers} />}
        </div>
      </main>

      <footer className="foot">
        <span className="foot__api">{configured ? apiBaseUrl() : "API not configured"}</span>
        <span>Public e-commerce clickstream &middot; same shape as Flume sessions</span>
      </footer>
    </div>
  );
}
