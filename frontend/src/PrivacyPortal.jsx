import React, { useState } from "react";

const BASE = import.meta.env.VITE_API_BASE || "";

async function apiCall(method, path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

const SIGNAL_CATEGORIES = [
  "coding_session", "debugging_trace", "ai_prompt_category", "commit_metadata",
  "pr_review_quality", "interview_transcript_embedding", "architecture_decision_tag",
  "onboarding_task_completion", "collaboration_frequency", "job_performance_rating",
];

export default function PrivacyPortal({ onBack }) {
  const [engineerId, setEngineerId] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [consentStatus, setConsentStatus] = useState(null);
  const [signals, setSignals] = useState(null);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  async function handleLookup(e) {
    e.preventDefault();
    if (!engineerId.trim()) return;
    setLoading(true);
    setError("");
    try {
      const [consent, sigs] = await Promise.all([
        apiCall("GET", `/api/engineer/consent?engineer_id=${encodeURIComponent(engineerId)}`),
        apiCall("GET", `/api/engineer/signals?engineer_id=${encodeURIComponent(engineerId)}`),
      ]);
      setConsentStatus(consent);
      setSignals(sigs);
      if (consent.consent_record?.signal_categories) {
        setSelectedCategories(consent.consent_record.signal_categories);
      }
      setSubmitted(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleGrantConsent() {
    setLoading(true);
    setError("");
    setSuccessMsg("");
    try {
      await apiCall("POST", "/api/engineer/consent", {
        engineer_id: engineerId,
        signal_categories: selectedCategories,
      });
      setSuccessMsg("Consent granted successfully.");
      await handleRefresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleRevokeConsent() {
    if (!confirm("Revoke consent? This will stop new signal collection.")) return;
    setLoading(true);
    setError("");
    setSuccessMsg("");
    try {
      await apiCall("DELETE", "/api/engineer/consent", { engineer_id: engineerId });
      setSuccessMsg("Consent revoked. No new signals will be collected.");
      await handleRefresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleErasure() {
    if (!confirm("Request data erasure? This severs all links between your identity and your signals. This cannot be undone.")) return;
    setLoading(true);
    setError("");
    setSuccessMsg("");
    try {
      const res = await apiCall("POST", "/api/engineer/erasure-request", { engineer_id: engineerId });
      setSuccessMsg(res.message || "Erasure request submitted.");
      setSignals(null);
      setConsentStatus(null);
      setSubmitted(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    const [consent, sigs] = await Promise.all([
      apiCall("GET", `/api/engineer/consent?engineer_id=${encodeURIComponent(engineerId)}`),
      apiCall("GET", `/api/engineer/signals?engineer_id=${encodeURIComponent(engineerId)}`),
    ]);
    setConsentStatus(consent);
    setSignals(sigs);
  }

  function toggleCategory(cat) {
    setSelectedCategories(prev =>
      prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]
    );
  }

  const hasConsent = consentStatus?.has_consent;

  return (
    <div style={{ maxWidth: "640px", margin: "0 auto", padding: "2rem 1rem" }}>
      <button className="btn-ghost" onClick={onBack} style={{ marginBottom: "1rem" }}>← Back</button>

      <h2>Engineer Privacy Portal</h2>
      <p className="muted" style={{ marginBottom: "1.5rem" }}>
        View and manage the data collected about you. You control what's collected and can request erasure at any time.
      </p>

      {!submitted ? (
        <form className="card" onSubmit={handleLookup}>
          <label>Your email / engineer ID</label>
          <input type="email" value={engineerId} required
            placeholder="you@company.com"
            onChange={e => setEngineerId(e.target.value)} />
          {error && <p className="error">{error}</p>}
          <button type="submit" disabled={loading}>{loading ? "Looking up…" : "View my data"}</button>
        </form>
      ) : (
        <div>
          {error && <div className="error" style={{ marginBottom: "1rem" }}>{error}</div>}
          {successMsg && <div style={{ background: "#dafbe1", border: "1px solid #2da44e", borderRadius: "6px", padding: "10px 14px", marginBottom: "1rem", color: "#116329" }}>{successMsg}</div>}

          {/* Consent status */}
          <div className="card" style={{ marginBottom: "1rem" }}>
            <h3 style={{ marginBottom: "0.5rem" }}>Consent Status</h3>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span className={`tag ${hasConsent ? "tag-green" : ""}`} style={!hasConsent ? { background: "#ffebe9", color: "#d1242f" } : {}}>
                {hasConsent ? "✓ Active" : "✗ No consent / Revoked"}
              </span>
              {consentStatus?.consent_record?.granted_at && (
                <span className="muted" style={{ fontSize: "12px" }}>
                  Since {new Date(consentStatus.consent_record.granted_at).toLocaleDateString()}
                </span>
              )}
            </div>

            {/* Category selection */}
            <div style={{ marginTop: "1rem" }}>
              <p className="muted" style={{ fontSize: "13px", marginBottom: "8px" }}>
                Signal categories — select what you allow us to collect:
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                {SIGNAL_CATEGORIES.map(cat => (
                  <button key={cat} type="button"
                    className={selectedCategories.includes(cat) ? "" : "btn-ghost"}
                    style={{ padding: "4px 10px", fontSize: "12px" }}
                    onClick={() => toggleCategory(cat)}>
                    {cat.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ display: "flex", gap: "8px", marginTop: "1rem" }}>
              <button onClick={handleGrantConsent} disabled={loading || selectedCategories.length === 0}>
                {hasConsent ? "Update consent" : "Grant consent"}
              </button>
              {hasConsent && (
                <button className="btn-secondary" onClick={handleRevokeConsent} disabled={loading}>
                  Revoke consent
                </button>
              )}
            </div>
          </div>

          {/* Signal summary */}
          <div className="card" style={{ marginBottom: "1rem" }}>
            <h3 style={{ marginBottom: "0.5rem" }}>Your Signals</h3>
            {signals && signals.signal_count === 0 ? (
              <div className="muted">No signals collected yet.</div>
            ) : signals ? (
              <>
                <div className="muted" style={{ marginBottom: "0.75rem" }}>
                  {signals.signal_count} signal{signals.signal_count !== 1 ? "s" : ""} collected
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      <th style={{ padding: "6px 10px", textAlign: "left" }}>Type</th>
                      <th style={{ padding: "6px 10px", textAlign: "left" }}>Source</th>
                      <th style={{ padding: "6px 10px", textAlign: "left" }}>Collected</th>
                    </tr>
                  </thead>
                  <tbody>
                    {signals.signals.slice(0, 20).map(s => (
                      <tr key={s.signal_id} style={{ borderTop: "1px solid #eaeef2" }}>
                        <td style={{ padding: "6px 10px" }} className="muted">{s.signal_type?.replace(/_/g, " ")}</td>
                        <td style={{ padding: "6px 10px" }} className="muted">{s.source_system}</td>
                        <td style={{ padding: "6px 10px" }} className="muted">{new Date(s.collected_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {signals.signal_count > 20 && (
                  <div className="muted" style={{ marginTop: "8px", fontSize: "12px" }}>
                    Showing 20 of {signals.signal_count} signals.
                  </div>
                )}
              </>
            ) : null}
          </div>

          {/* Erasure request */}
          <div className="card" style={{ border: "1px solid #ffcecb" }}>
            <h3 style={{ marginBottom: "0.5rem", color: "#d1242f" }}>Data Erasure</h3>
            <p className="muted" style={{ fontSize: "13px", marginBottom: "0.75rem" }}>
              Requesting erasure severs all links between your identity and your signals.
              Your anonymised signals remain in aggregate model training data but cannot be
              traced back to you. This action is irreversible.
            </p>
            <button style={{ background: "#d1242f", color: "#fff", border: "none" }}
              onClick={handleErasure} disabled={loading}>
              Request data erasure
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
