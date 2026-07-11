import React, { useEffect, useRef, useState } from "react";
import {
  startInterview,
  sendInterviewMessage,
  completeInterview,
  saveInterviewReview,
  uploadInterviewRecording,
  checkBanStatus,
  banUser,
  updateTabChanges,
} from "./api.js";
import { useVoice } from "./useVoice.js";
import { useVideoCheck } from "./useVideoCheck.js";
import { useNetworkCheck } from "./useNetworkCheck.js";
import { useInterviewRecorder } from "./useInterviewRecorder.js";
import { useScreenShare } from "./useScreenShare.js";

const SAMPLE_JD = `Senior Python Engineer
- 5+ years building REST APIs in Python
- Strong experience with FastAPI and PostgreSQL
- Nice to have: Docker, AWS`;

const SAMPLE_RESUME = `Jane Doe — Software Engineer
6 years of Python experience building REST APIs with FastAPI.
Extensive PostgreSQL and Docker work, deployed on AWS.
Led a team of 3 engineers on a payments service.`;

function bandColor(band) {
  return (
    {
      strong_advance: "#1a7f37",
      advance: "#2da44e",
      borderline: "#bf8700",
      hold: "#d1242f",
      do_not_advance: "#82071e",
    }[band] || "#57606a"
  );
}

function CheckItem({ label, status, detail, error }) {
  const icon =
    status === "ready" ? "✓" : status === "checking" ? "…" : status === "error" ? "✗" : "○";
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

export default function InterviewRoom({ health }) {
  const [jd, setJd] = useState(SAMPLE_JD);
  const [resume, setResume] = useState(SAMPLE_RESUME);
  const [sessionId, setSessionId] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [phase, setPhase] = useState("idle"); // idle | preflight | active | complete
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [input, setInput] = useState("");
  const [voiceMode, setVoiceMode] = useState(true);
  const [conversationState, setConversationState] = useState(null);
  const [results, setResults] = useState(null);
  const [reviewSaved, setReviewSaved] = useState(null);
  const [preflightDone, setPreflightDone] = useState(false);
  const [banned, setBanned] = useState(false);
  const [tabChangeWarnings, setTabChangeWarnings] = useState(0);
  const [showTabWarning, setShowTabWarning] = useState(false);
  const [tabWarningCountdown, setTabWarningCountdown] = useState(0);
  const chatEndRef = useRef(null);
  const preflightRef = useRef({ video: false, network: false, screenShare: false, metrics: null });
  const warningIntervalRef = useRef(null);

  const { supported, listening, speaking, speak, listen, stopSpeaking } = useVoice();
  const video = useVideoCheck();
  const network = useNetworkCheck();
  const { recording, startRecording, stopRecording } = useInterviewRecorder(video.stream);
  const {
    status: screenShareStatus,
    error: screenShareError,
    stream: screenShareStream,
    MAX_WARNINGS: MAX_TAB_WARNINGS,
    checkScreenShare,
    stopScreenShare,
  } = useScreenShare();

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  // Check if candidate is banned on load
  useEffect(() => {
    const fetchBanStatus = async () => {
      try {
        const status = await checkBanStatus("cand_1");
        if (status.banned) {
          setBanned(true);
          setError(`You are banned: ${status.reason}`);
        }
      } catch (e) {
        // Ignore if backend is down
      }
    };
    fetchBanStatus();
  }, []);

  // Handle visibility change for tab switching
  useEffect(() => {
    if (phase === "active" && sessionId) {
      const handleVisibilityChangeEvent = async () => {
        if (document.hidden && !banned) {
          if (tabChangeWarnings < MAX_TAB_WARNINGS - 1) {
            // Show warning
            const newWarnings = tabChangeWarnings + 1;
            setTabChangeWarnings(newWarnings);
            setShowTabWarning(true);
            setTabWarningCountdown(3);
            await updateTabChanges(sessionId, newWarnings);
            
            if (warningIntervalRef.current) clearInterval(warningIntervalRef.current);
            let countdown = 3;
            warningIntervalRef.current = setInterval(() => {
              countdown -= 1;
              setTabWarningCountdown(countdown);
              if (countdown <= 0) {
                clearInterval(warningIntervalRef.current);
                setShowTabWarning(false);
              }
            }, 1000);
          } else {
            // Ban
            await banUser("cand_1", "Too many tab changes during interview");
            setBanned(true);
            await handleComplete(sessionId, true);
          }
        }
      };
      
      document.addEventListener("visibilitychange", handleVisibilityChangeEvent);
      return () => {
        document.removeEventListener("visibilitychange", handleVisibilityChangeEvent);
        if (warningIntervalRef.current) clearInterval(warningIntervalRef.current);
      };
    }
  }, [phase, sessionId, tabChangeWarnings, banned, MAX_TAB_WARNINGS]);

  // Reset warnings when starting a new interview
  const resetTabWarnings = () => {
    setTabChangeWarnings(0);
    setShowTabWarning(false);
    setTabWarningCountdown(0);
    if (warningIntervalRef.current) clearInterval(warningIntervalRef.current);
  };

  const preflightReady =
    video.status === "ready" && network.status === "ready" && screenShareStatus === "ready" && preflightDone;

  async function runPreflight() {
    setPhase("preflight");
    setError("");
    setPreflightDone(false);
    preflightRef.current = { video: false, network: false, screenShare: false, metrics: null };

    const videoOk = await video.check();
    preflightRef.current.video = videoOk;

    const networkOk = await network.check();
    preflightRef.current.network = networkOk;
    preflightRef.current.metrics = network.metrics;

    const screenShareOk = await checkScreenShare();
    preflightRef.current.screenShare = screenShareOk;

    if (videoOk && networkOk && screenShareOk) setPreflightDone(true);
  }

  async function speakAria(text) {
    if (voiceMode && supported.tts) {
      return new Promise((resolve) => speak(text, resolve));
    }
  }

  async function saveForReview(data, videoBlob, isBanned = false) {
    try {
      const saved = await saveInterviewReview({
        session_id: data.session_id || sessionId,
        transcript: data.transcript || transcript,
        score: data.score,
        feedback: data.feedback,
        handoff: data.handoff,
        preflight: preflightRef.current,
        has_video: !!videoBlob,
      });
      setReviewSaved(saved);
      if (videoBlob) {
        await uploadInterviewRecording(
          data.session_id || sessionId,
          videoBlob,
          saved.review_id
        );
      }
    } catch (e) {
      console.warn("Could not save review:", e.message);
    }
  }

  async function handleStart() {
    if (!preflightReady) {
      setError("Camera, network, and screen share checks must pass before starting.");
      return;
    }

    setLoading(true);
    setError("");
    setTranscript([]);
    setResults(null);
    setReviewSaved(null);
    resetTabWarnings();

    try {
      startRecording();
      const data = await startInterview({
        job_description: jd,
        resume,
        candidate_id: "cand_1",
      });
      setSessionId(data.session_id);
      setTranscript(data.transcript || []);
      setConversationState(data.conversation_state);
      setPhase("active");
      if (data.message) await speakAria(data.message);
      if (data.is_complete) await handleComplete(data.session_id);
    } catch (e) {
      setError(e.message);
      await stopRecording();
      await stopScreenShare();
    } finally {
      setLoading(false);
    }
  }

  async function handleSend(text) {
    const message = text.trim();
    if (!message || !sessionId || loading) return;

    setInput("");
    setLoading(true);
    setError("");
    stopSpeaking();

    try {
      const data = await sendInterviewMessage(sessionId, message);
      setTranscript(data.transcript || []);
      setConversationState(data.conversation_state);
      if (data.message) await speakAria(data.message);
      if (data.is_complete) await handleComplete(sessionId);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleComplete(sid, isBanned = false) {
    const videoBlob = await stopRecording();
    await stopScreenShare();
    try {
      const data = await completeInterview(sid || sessionId);
      setResults(data);
      setPhase("complete");
      await saveForReview(data, videoBlob, isBanned);
    } catch (e) {
      setError(e.message);
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

  async function handleReset() {
    stopSpeaking();
    await stopRecording();
    await stopScreenShare();
    video.stop();
    setSessionId(null);
    setTranscript([]);
    setPhase("idle");
    setResults(null);
    setReviewSaved(null);
    setConversationState(null);
    setPreflightDone(false);
    setError("");
    setInput("");
    resetTabWarnings();
  }

  const stateLabel = conversationState?.state?.replace(/_/g, " ") || "";

  if (banned) {
    return (
      <div className="interview-room">
        <div className="interview-setup" style={{ textAlign: "center" }}>
          <h2 style={{ color: "#d1242f" }}>Access Denied</h2>
          <p className="muted">You have been banned from using the interview system.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="interview-room">
      {phase === "idle" && (
        <div className="interview-setup">
          <div className="setup-col">
            <h2>Start your AI interview</h2>
            <p className="muted">
              Aria will conduct a voice screening. Before starting, we verify your
              camera, network connection, and screen share. Your session is saved for human review.
            </p>
            {health?.mock && (
              <p className="notice">
                Backend is in MOCK mode. Set <code>USE_MOCK_LLM=</code> (empty) in
                backend/.env and restart the server to use Gemini.
              </p>
            )}
            <label>Job Description</label>
            <textarea value={jd} onChange={(e) => setJd(e.target.value)} rows={6} />
            <label>Your Resume</label>
            <textarea value={resume} onChange={(e) => setResume(e.target.value)} rows={6} />
            <div className="interview-controls">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={voiceMode}
                  onChange={(e) => setVoiceMode(e.target.checked)}
                />
                Voice mode (Aria speaks aloud)
              </label>
              <button onClick={runPreflight} disabled={loading || !jd || !resume}>
                Check camera, network, and screen share
              </button>
            </div>
            {error && <p className="error">Error: {error}</p>}
          </div>
          <div className="setup-col aria-preview">
            <div className="aria-avatar">A</div>
            <h3>Aria</h3>
            <p className="muted">Your AI interviewer</p>
            <ul className="aria-features">
              <li>Camera required before interview</li>
              <li>Network speed verified</li>
              <li>Screen share required (entire screen)</li>
              <li>Session recorded for human review</li>
              <li>Tab switching will trigger warnings</li>
            </ul>
          </div>
        </div>
      )}

      {phase === "preflight" && (
        <div className="preflight-panel card">
          <h2>Pre-interview checks</h2>
          <p className="muted">
            All checks must pass before you can start the interview.
          </p>

          <div className="preflight-grid">
            <div className="preflight-checks">
              <CheckItem
                label="Camera"
                status={video.status}
                detail={
                  video.status === "ready"
                    ? "Webcam is active and enabled"
                    : video.status === "checking"
                    ? "Requesting camera access…"
                    : "Camera must be enabled"
                }
                error={video.error}
              />
              <CheckItem
                label="Network"
                status={network.status}
                detail={
                  network.metrics
                    ? `${network.metrics.latencyMs}ms latency`
                    : network.status === "checking"
                    ? "Testing connection…"
                    : "Stable connection required"
                }
                error={network.error}
              />
              <CheckItem
                label="Screen Share"
                status={screenShareStatus}
                detail={
                  screenShareStatus === "ready"
                    ? "Screen sharing active (entire screen)"
                    : screenShareStatus === "checking"
                    ? "Requesting screen share…"
                    : "Screen share must be enabled (entire screen only)"
                }
                error={screenShareError}
              />
              {!preflightDone && (
                <button className="btn-secondary" onClick={runPreflight}>
                  Re-run checks
                </button>
              )}
            </div>

            <div className="video-preview-wrap">
              <video
                ref={video.videoRef}
                autoPlay
                playsInline
                muted
                className="video-preview"
              />
              {video.status !== "ready" && (
                <div className="video-placeholder">
                  {video.status === "checking"
                    ? "Checking camera…"
                    : "Camera preview will appear here"}
                </div>
              )}
              {screenShareStream && (
                <video
                  autoPlay
                  playsInline
                  muted
                  className="screen-share-preview"
                  ref={(el) => {
                    if (el) el.srcObject = screenShareStream;
                  }}
                />
              )}
            </div>
          </div>

          <div className="preflight-actions">
            <button className="btn-secondary" onClick={() => setPhase("idle")}>
              Back
            </button>
            <button
              onClick={handleStart}
              disabled={!preflightReady || loading}
            >
              {loading ? "Starting interview…" : "Start interview with Aria"}
            </button>
          </div>
          {error && <p className="error">Error: {error}</p>}
        </div>
      )}

      {(phase === "active" || phase === "complete") && (
        <div className="interview-active">
          {showTabWarning && (
            <div className="warning-overlay">
              <div className="warning-card">
                <h3>⚠️ Warning</h3>
                <p>
                  Tab change detected! Warning {tabChangeWarnings}/{MAX_TAB_WARNINGS}.
                </p>
                <p className="muted">
                  Returning to the interview in {tabWarningCountdown}s...
                </p>
              </div>
            </div>
          )}
          <div className="interview-header">
            <div className="aria-status">
              <div className={`aria-avatar small ${speaking ? "speaking" : ""}`}>
                A
              </div>
              <div>
                <strong>Aria</strong>
                <div className="muted">
                  {recording && "● Recording · "}
                  {speaking
                    ? "Speaking…"
                    : listening
                    ? "Listening…"
                    : loading
                    ? "Thinking…"
                    : stateLabel || "Interview in progress"}
                </div>
              </div>
            </div>
            <div className="header-actions">
              <video
                ref={video.videoRef}
                autoPlay
                playsInline
                muted
                className="video-pip"
              />
              {screenShareStream && (
                <video
                  autoPlay
                  playsInline
                  muted
                  className="screen-share-pip"
                  ref={(el) => {
                    if (el) el.srcObject = screenShareStream;
                  }}
                />
              )}
              <label className="toggle compact">
                <input
                  type="checkbox"
                  checked={voiceMode}
                  onChange={(e) => setVoiceMode(e.target.checked)}
                />
                Voice
              </label>
              <button className="btn-secondary" onClick={handleReset}>
                End & restart
              </button>
            </div>
          </div>

          <div className="chat-window">
            {transcript.map((entry, i) => (
              <div
                key={i}
                className={`chat-bubble ${entry.speaker === "aria" ? "aria" : "candidate"}`}
              >
                <span className="bubble-label">
                  {entry.speaker === "aria" ? "Aria" : "You"}
                </span>
                <p>{entry.text}</p>
              </div>
            ))}
            {loading && (
              <div className="chat-bubble aria typing">
                <span className="bubble-label">Aria</span>
                <p className="typing-dots">
                  <span>.</span>
                  <span>.</span>
                  <span>.</span>
                </p>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {phase === "active" && (
            <div className="input-bar">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend(input)}
                placeholder="Type your answer or use the mic…"
                disabled={loading || speaking}
              />
              {supported.stt && (
                <button
                  className={`mic-btn ${listening ? "active" : ""}`}
                  onClick={handleMic}
                  disabled={loading || speaking}
                  title="Speak your answer"
                >
                  {listening ? "●" : "🎤"}
                </button>
              )}
              <button
                onClick={() => handleSend(input)}
                disabled={loading || speaking || !input.trim()}
              >
                Send
              </button>
            </div>
          )}

          {error && <p className="error">Error: {error}</p>}

          {results && (
            <div className="interview-results">
              <h3>Interview complete</h3>
              {results.mock && (
                <p className="notice">
                  MOCK mode — set USE_MOCK_LLM empty in backend/.env and restart.
                </p>
              )}
              {reviewSaved?.saved && (
                <p className="notice success">
                  Saved for human review (ID: {reviewSaved.review_id})
                </p>
              )}
              <div className="score-row">
                <div
                  className="score-badge"
                  style={{ background: bandColor(results.score?.band) }}
                >
                  {results.score?.overall_score}
                </div>
                <div>
                  <div className="band">
                    {results.score?.band?.replace(/_/g, " ")}
                  </div>
                  <div className="muted">{results.feedback?.headline}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
