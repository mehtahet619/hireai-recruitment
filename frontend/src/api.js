const BASE = import.meta.env.VITE_API_BASE || "";

async function req(method, path, body, token) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

const get = (path, token) => req("GET", path, null, token);
const post = (path, body, token) => req("POST", path, body, token);
const patch = (path, body, token) => req("PATCH", path, body, token);

export const getHealth = () => get("/api/health");

// Employer auth
export const employerRegister = (data) => post("/api/employer/register", data);
export const employerLogin = (data) => post("/api/employer/login", data);
export const employerMe = (token) => get("/api/employer/me", token);

// Jobs (public)
export const listJobs = () => get("/api/jobs");
export const getJob = (jobId) => get(`/api/jobs/${jobId}`);

// Jobs (employer)
export const createJob = (data, token) => post("/api/employer/jobs", data, token);
export const listEmployerJobs = (token) => get("/api/employer/jobs", token);
export const updateJob = (jobId, data, token) => patch(`/api/employer/jobs/${jobId}`, data, token);
export const getJobApplicants = (jobId, token) => get(`/api/employer/jobs/${jobId}/applicants`, token);
export const getApplicant = (appId, token) => get(`/api/employer/applicants/${appId}`, token);

// Candidate apply flow
export const applyForJob = (data) => post("/api/apply", data);
export const sendApplicationMessage = (sessionId, message) =>
  post("/api/apply/message", { session_id: sessionId, message });
export const completeApplication = (sessionId) =>
  post("/api/apply/complete", { session_id: sessionId });

// Legacy interview (keep for compatibility)
export const startInterview = (payload) => post("/api/interview/start", payload);
export const sendInterviewMessage = (sessionId, message) =>
  post("/api/interview/message", { session_id: sessionId, message });
export const completeInterview = (sessionId) =>
  post("/api/interview/complete", { session_id: sessionId });
export const saveInterviewReview = (payload) =>
  post("/api/interview/save-review", payload);
export async function uploadInterviewRecording(sessionId, blob, reviewId = "") {
  const form = new FormData();
  form.append("session_id", sessionId);
  if (reviewId) form.append("review_id", reviewId);
  form.append("recording", blob, `interview-${sessionId.slice(0, 8)}.webm`);
  const res = await fetch(`${BASE}/api/interview/upload-recording`, { method: "POST", body: form });
  if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail || d; } catch (_) {} throw new Error(d); }
  return res.json();
}
export const checkBanStatus = (candidateId) => post("/api/ban/check", { candidate_id: candidateId });
export const banUser = (candidateId, reason) => post("/api/ban/user", { candidate_id: candidateId, reason });
export const updateTabChanges = (sessionId, warningsCount) =>
  post("/api/interview/update-tab-changes", { session_id: sessionId, warnings_count: warningsCount });
