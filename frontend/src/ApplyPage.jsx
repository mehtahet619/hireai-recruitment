import React, { useEffect, useState, useRef, useCallback } from "react";
import { getJob, applyForJob, sendApplicationMessage, completeApplication } from "./api.js";
import { useVoice } from "./useVoice.js";
import { useVideoCheck } from "./useVideoCheck.js";
import { useNetworkCheck } from "./useNetworkCheck.js";
import { useScreenShare } from "./useScreenShare.js";
import { useInterviewRecorder } from "./useInterviewRecorder.js";
import { useGoogleAuth, GOOGLE_CLIENT_ID } from "./useGoogleAuth.js";

const TAB_ABSENCE_LIMIT_MS = 5000; // 5 seconds away = 1 violation
const MAX_VIOLATIONS = 3;          // ban on 3rd violation

function bandColor(band) {
  return ({ strong_advance: "#1a7f37", advance: "#2da44e", borderline: "#bf8700",
    hold: "#d1242f", do_not_advance: "#82071e" }[band] || "#57606a");
}

function CheckItem({ label, status, detail, error }) {
  const icon = status === "ready" ? "✓" : status === "checking" ? "…" : status === "error" ? "✗" : "○";
  return (
    <div className={`check-item ${status}`}>
      <span className="check-icon">{icon}</span>
      <div>
        <strong>{label}</strong>
        {detail && <div className="muted">{detail}</div>}
        {error && <div className="error small">{error}</div>}
      </div>
    </div>
  );
}

export default function ApplyPage({ jobId, onBack }) {
  const [job, setJob] = useState(null);
  // phases: form | preflight | interview | complete | banned
  const [phase, setPhase] = useState("form");
  const [form, setForm] = useState({ name: "", email: "", resume: "" });
  const [sessionId, setSessionId] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState(null);
  const [voiceMode, setVoiceMode] = useState(true);
  const [preflightDone, setPreflightDone] = useState(false);

  // Tab-switch proctoring
  const [violations, setViolations] = useState(0);
  const [showTabWarning, setShowTabWarning] = useState(false);
  const [tabCountdown, setTabCountdown] = useState(0);
  const tabHiddenAt = useRef(null);
  const tabTimerRef = useRef(null);
  const countdownRef = useRef(null);
  const sessionIdRef = useRef(null);
  const violationsRef = useRef(0);

  const chatEndRef = useRef(null);

  const { supported, listening, speaking, speak, listen, stopSpeaking } = useVoice();
  const video = useVideoCheck();
  const network = useNetworkCheck();
  const { status: screenStatus, error: screenError, stream: screenStream,
    checkScreenShare, stopScreenShare } = useScreenShare();
  const { recording, startRecording, stopRecording } = useInterviewRecorder(video.stream);

  // Google Sign-In pre-fills name + email
  useGoogleAuth("candidate-google-btn", ({ name, email }) => {
    setForm((f) => ({ ...f, name: name || f.name, email: email || f.email }));
  });

  useEffect(() => {
    getJob(jobId).then(setJob).catch((e) => setError(e.message));
  }, [jobId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  // Keep ref in sync so visibility handler always has latest
  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
  useEffect(() => { violationsRef.current = violations; }, [violations]);

  // ── Tab-switch monitor (only active during interview) ──────────────────
  useEffect(() => {
    if (phase !== "interview") return;

    function onVisibility() {
      if (document.hidden) {
        // started hiding — record time
        tabHiddenAt.current = Date.now();
        tabTimerRef.current = setTimeout(() => {
          // still hidden after limit — count violation
          const newCount = violationsRef.current + 1;
          setViolations(newCount);
          violationsRef.current = newCount;

          if (newCount >= MAX_VIOLATIONS) {
            handleBan();
          } else {
            setShowTabWarning(true);
            setTabCountdown(3);
            let c = 3;
            clearInterval(countdownRef.current);
            countdownRef.current = setInterval(() => {
              c -= 1;
              setTabCountdown(c);
              if (c <= 0) {
                clearInterval(countdownRef.current);
                setShowTabWarning(false);
              }
            }, 1000);
          }
        }, TAB_ABSENCE_LIMIT_MS);
      } else {
        // came back — clear the timer if they returned quickly
        clearTimeout(tabTimerRef.current);
        tabHiddenAt.current = null;
      }
    }

    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      clearTimeout(tabTimerRef.current);
      clearInterval(countdownRef.current);
    };
  }, [phase]);

  async function handleBan() {
    setPhase("banned");
    stopSpeaking();
    await stopRecording();
    stopScreenShare();
    // force-complete so score is saved
    const sid = sessionIdRef.current;
    if (sid) {
      try { await completeApplication(sid); } catch (_) {}
    }
  }

  // ── Preflight ──────────────────────────────────────────────────────────
  async function runPreflight() {
    setPreflightDone(false);
    setError("");
    await video.check();
    await network.check();
    await checkScreenShare();
    setPreflightDone(true);
  }

  const preflightReady =
    video.status === "ready" &&
    network.status === "ready" &&
    screenStatus === "ready" &&
    preflightDone;

  // ── Submit form → start interview ──────────────────────────────────────
  async function handleSubmit(e) {
    e.preventDefault();
    setPhase("preflight");
    // auto-run checks
    setTimeout(runPreflight, 100);
  }

  async function handleStartInterview() {
    if (!preflightReady) return;
    setLoading(true);
    setError("");
    try {
      startRecording();
      const data = await applyForJob({
        job_id: jobId,
        candidate_name: form.name,
        candidate_email: form.email,
        resume: form.resume,
      });
      setSessionId(data.session_id);
      setTranscript(data.transcript || []);
      setPhase("interview");
      if (data.message && voiceMode && supported.tts) {
        await new Promise((r) => speak(data.message, r));
      }
      if (data.is_complete) await finishInterview(data.session_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  // ── Chat ───────────────────────────────────────────────────────────────
  async function handleSend(text) {
    const message = text.trim();
    if (!message || !sessionId || loading) return;
    setInput("");
    setLoading(true);
    setError("");
    stopSpeaking();
    try {
      const data = await sendApplicationMessage(sessionId, message);
      setTranscript(data.transcript || []);
      if (data.message && voiceMode && supported.tts) {
        await new Promise((r) => speak(data.message, r));
      }
      if (data.is_complete) await finishInterview(sessionId);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function finishInterview(sid) {
    setLoading(true);
    try {
      const blob = await stopRecording();
      stopScreenShare();
      const data = await completeApplication(sid || sessionId);
      setResults(data);
      setPhase("complete");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleMic() {
    if (listening) return;
    try {
      const text = await listen();
      if (text) await handleSend(text);
    } catch (e) {
      setError(e.message);
    }
  }

  // ── Render helpers ─────────────────────────────────────────────────────
  if (!job && !error) return <div className="page-center muted">Loading job…</div>;

  if (phase === "banned") {
    return (
      <div className="apply-page">
        <div className="banned-card card">
          <div className="banned-icon">🚫</div>
          <h2>Interview terminated</h2>
          <p>You were away from the tab {MAX_VIOLATIONS} times for more than {TAB_ABSENCE_LIMIT_MS / 1000} seconds.</p>
          <p className="muted">Your session has been flagged and your results submitted to the employer.</p>
          <button className="btn-secondary" onClick={onBack}>Back to jobs</button>
        </div>
      </div>
    );
  }

  return (
    <div className="apply-page">
      {phase !== "complete" && (
        <button className="btn-ghost back-btn" onClick={onBack}>← Back to jobs</button>
      )}

      {job && phase !== "complete" && (
        <div className="job-banner">
          <h2>{job.title}</h2>
          <div className="job-meta">
            <span className="tag">{job.employment_type}</span>
            <span className="tag">{job.location}</span>
            <span className="muted">{job.company_name}</span>
          </div>
        </div>
      )}

      {/* ── FORM ── */}
      {phase === "form" && (
        <div className="apply-form-wrap">
          <div className="apply-form card">
            <h3>Your application</h3>
            <p className="muted">
              After submitting we'll verify your camera, mic, network, and screen share — then Aria
              will interview you immediately.
            </p>
            {error && <p className="error">{error}</p>}
            {GOOGLE_CLIENT_ID && (
              <>
                <div id="candidate-google-btn" style={{ marginBottom: "12px" }} />
                <div className="auth-divider"><span>or fill in manually</span></div>
              </>
            )}
            <form onSubmit={handleSubmit}>
              <label>Full name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Jane Doe" required />
              <label>Email</label>
              <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="jane@example.com" required />
              <label>Resume / CV</label>
              <textarea value={form.resume} onChange={(e) => setForm({ ...form, resume: e.target.value })}
                rows={10} placeholder="Paste your resume text here…" required />
              <div className="form-footer">
                <label className="toggle">
                  <input type="checkbox" checked={voiceMode}
                    onChange={(e) => setVoiceMode(e.target.checked)} />
                  Voice mode (Aria speaks aloud)
                </label>
                <button type="submit" disabled={loading}>
                  Continue to checks →
                </button>
              </div>
            </form>
          </div>
          {job && (
            <div className="jd-preview card">
              <h4>Job description</h4>
              <pre className="jd-text">{job.description}</pre>
            </div>
          )}
        </div>
      )}

      {/* ── PREFLIGHT ── */}
      {phase === "preflight" && (
        <div className="preflight-panel card">
          <h2>Pre-interview checks</h2>
          <p className="muted">All checks must pass before you can start.</p>

          <div className="preflight-grid">
            <div className="preflight-checks">
              <CheckItem
                label="Camera"
                status={video.status}
                detail={video.status === "ready" ? "Webcam active" : video.status === "checking" ? "Requesting camera…" : "Camera required"}
                error={video.error}
              />
              <CheckItem
                label="Microphone"
                status={video.status} // mic is part of getUserMedia (audio:true)
                detail={video.status === "ready" ? "Audio active" : video.status === "checking" ? "Requesting mic…" : "Microphone required"}
                error={null}
              />
              <CheckItem
                label="Network"
                status={network.status}
                detail={network.metrics ? `${network.metrics.latencyMs}ms latency` : network.status === "checking" ? "Testing connection…" : "Connection required"}
                error={network.error}
              />
              <CheckItem
                label="Screen share"
                status={screenStatus}
                detail={screenStatus === "ready" ? "Screen sharing active" : screenStatus === "checking" ? "Requesting screen…" : "Full-screen share required"}
                error={screenError}
              />
              <div className="preflight-rules">
                <strong>During the interview:</strong>
                <ul>
                  <li>Do not switch tabs or minimize</li>
                  <li>Leaving for &gt;{TAB_ABSENCE_LIMIT_MS / 1000}s counts as a violation</li>
                  <li>{MAX_VIOLATIONS} violations = automatic ban</li>
                </ul>
              </div>
              {preflightDone && !preflightReady && (
                <button className="btn-secondary" onClick={runPreflight}>Re-run checks</button>
              )}
            </div>

            <div className="video-preview-wrap">
              <video ref={video.videoRef} autoPlay playsInline muted className="video-preview" />
              {video.status !== "ready" && (
                <div className="video-placeholder">
                  {video.status === "checking" ? "Checking camera…" : "Camera preview"}
                </div>
              )}
              {screenStream && (
                <video autoPlay playsInline muted className="screen-share-preview"
                  ref={(el) => { if (el) el.srcObject = screenStream; }} />
              )}
            </div>
          </div>

          {error && <p className="error">{error}</p>}

          <div className="preflight-actions">
            <button className="btn-secondary" onClick={() => setPhase("form")}>Back</button>
            <button onClick={handleStartInterview} disabled={!preflightReady || loading}>
              {loading ? "Starting…" : "Start interview with Aria"}
            </button>
          </div>
        </div>
      )}

      {/* ── INTERVIEW ── */}
      {phase === "interview" && (
        <div className="interview-active">
          {/* Tab warning overlay */}
          {showTabWarning && (
            <div className="warning-overlay">
              <div className="warning-card">
                <h3>⚠️ Tab switch detected</h3>
                <p>Violation {violations} of {MAX_VIOLATIONS}. One more and your interview will be terminated.</p>
                <p className="muted">Returning in {tabCountdown}s…</p>
              </div>
            </div>
          )}

          <div className="interview-header">
            <div className="aria-status">
              <div className={`aria-avatar small ${speaking ? "speaking" : ""}`}>A</div>
              <div>
                <strong>Aria</strong>
                <div className="muted">
                  {speaking ? "Speaking…" : listening ? "Listening…" : loading ? "Thinking…" : "Interview in progress"}
                </div>
              </div>
            </div>
            <div className="header-actions">
              <video ref={video.videoRef} autoPlay playsInline muted className="video-pip" />
              {screenStream && (
                <video autoPlay playsInline muted className="screen-share-pip"
                  ref={(el) => { if (el) el.srcObject = screenStream; }} />
              )}
              {violations > 0 && (
                <span className="violation-badge">⚠️ {violations}/{MAX_VIOLATIONS}</span>
              )}
              {recording && <span className="rec-dot">● REC</span>}
              <label className="toggle compact">
                <input type="checkbox" checked={voiceMode} onChange={(e) => setVoiceMode(e.target.checked)} />
                Voice
              </label>
            </div>
          </div>

          <div className="chat-window">
            {transcript.map((entry, i) => (
              <div key={i} className={`chat-bubble ${entry.speaker === "aria" ? "aria" : "candidate"}`}>
                <span className="bubble-label">{entry.speaker === "aria" ? "Aria" : "You"}</span>
                <p>{entry.text}</p>
              </div>
            ))}
            {loading && (
              <div className="chat-bubble aria typing">
                <span className="bubble-label">Aria</span>
                <p className="typing-dots"><span>.</span><span>.</span><span>.</span></p>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <div className="input-bar">
            <input type="text" value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend(input)}
              placeholder="Type your answer or use the mic…"
              disabled={loading || speaking} />
            {supported.stt && (
              <button className={`mic-btn ${listening ? "active" : ""}`}
                onClick={handleMic} disabled={loading || speaking} title="Speak">
                {listening ? "●" : "🎤"}
              </button>
            )}
            <button onClick={() => handleSend(input)} disabled={loading || speaking || !input.trim()}>
              Send
            </button>
          </div>

          {error && <p className="error" style={{ padding: "0 20px 12px" }}>{error}</p>}
        </div>
      )}

      {/* ── COMPLETE ── */}
      {phase === "complete" && results && (
        <div className="results-page">
          <div className="results-card card">
            <div className="results-header">
              <div className="aria-avatar" style={{ margin: "0 auto 16px" }}>A</div>
              <h2>Interview complete</h2>
              <p className="muted">Thanks {form.name} — here's how you did.</p>
            </div>

            <div className="score-row" style={{ justifyContent: "center", margin: "24px 0" }}>
              <div className="score-badge large" style={{ background: bandColor(results.score?.band) }}>
                {results.score?.overall_score}
              </div>
              <div>
                <div className="band" style={{ fontSize: "18px" }}>
                  {results.score?.band?.replace(/_/g, " ")}
                </div>
                <div className="muted">{results.feedback?.headline}</div>
              </div>
            </div>

            {results.score?.calculation && (
              <pre className="calc">{results.score.calculation}</pre>
            )}

            <p className="muted" style={{ textAlign: "center", marginTop: "16px" }}>
              Your results have been sent to the employer. Good luck!
            </p>
            <div style={{ textAlign: "center", marginTop: "20px" }}>
              <button className="btn-secondary" onClick={onBack}>Browse more jobs</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
