import React, { useEffect, useState } from "react";
import { listEmployerJobs, createJob, updateJob, getJobApplicants, getApplicant } from "./api.js";

function bandColor(band) {
  return ({ strong_advance: "#1a7f37", advance: "#2da44e", borderline: "#bf8700",
    hold: "#d1242f", do_not_advance: "#82071e" }[band] || "#57606a");
}

function NewJobForm({ token, onCreated }) {
  const [form, setForm] = useState({ title: "", description: "", location: "Remote", employment_type: "full-time" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await createJob(form, token);
      setForm({ title: "", description: "", location: "Remote", employment_type: "full-time" });
      onCreated();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="new-job-form card" onSubmit={handleSubmit}>
      <h3>Post a new opening</h3>
      {error && <p className="error">{error}</p>}
      <label>Job title</label>
      <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
        placeholder="Senior Python Engineer" required />
      <div className="form-row">
        <div>
          <label>Location</label>
          <input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} />
        </div>
        <div>
          <label>Type</label>
          <select value={form.employment_type} onChange={(e) => setForm({ ...form, employment_type: e.target.value })}>
            <option value="full-time">Full-time</option>
            <option value="part-time">Part-time</option>
            <option value="contract">Contract</option>
          </select>
        </div>
      </div>
      <label>Job description</label>
      <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
        rows={6} placeholder="Describe the role, responsibilities, and requirements…" required />
      <button type="submit" disabled={loading}>
        {loading ? "Posting…" : "Post opening"}
      </button>
    </form>
  );
}

function ApplicantDetail({ appId, token, onBack }) {
  const [app, setApp] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getApplicant(appId, token).then(setApp).finally(() => setLoading(false));
  }, [appId]);

  if (loading) return <div className="muted">Loading…</div>;
  if (!app) return <div className="error">Not found</div>;

  const score = app.score;
  return (
    <div className="applicant-detail">
      <button className="btn-ghost back-btn" onClick={onBack}>← Back to applicants</button>
      <div className="applicant-header">
        <h3>{app.candidate_name}</h3>
        <span className="muted">{app.candidate_email}</span>
        {score && (
          <div className="score-row" style={{ marginTop: "0.75rem" }}>
            <div className="score-badge" style={{ background: bandColor(score.band) }}>
              {score.overall_score}
            </div>
            <div>
              <div className="band">{score.band?.replace(/_/g, " ")}</div>
              <div className="muted">{app.feedback?.headline}</div>
            </div>
          </div>
        )}
      </div>
      {app.feedback?.open_questions_for_human?.length > 0 && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h4>Follow-up questions</h4>
          <ul>{app.feedback.open_questions_for_human.map((q, i) => <li key={i}>{q}</li>)}</ul>
        </div>
      )}
      <div className="card" style={{ marginTop: "1rem" }}>
        <h4>Resume</h4>
        <pre className="jd-text">{app.resume}</pre>
      </div>
      {app.transcript?.length > 0 && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h4>Interview transcript</h4>
          <div className="transcript-list">
            {app.transcript.map((t, i) => (
              <div key={i} className={`chat-bubble ${t.speaker === "aria" ? "aria" : "candidate"}`}>
                <span className="bubble-label">{t.speaker === "aria" ? "Aria" : app.candidate_name}</span>
                <p>{t.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ApplicantsList({ job, token, onBack }) {
  const [applicants, setApplicants] = useState(null);
  const [selectedApp, setSelectedApp] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getJobApplicants(job.job_id, token)
      .then((d) => setApplicants(d.applicants))
      .finally(() => setLoading(false));
  }, [job.job_id]);

  if (selectedApp) {
    return <ApplicantDetail appId={selectedApp} token={token} onBack={() => setSelectedApp(null)} />;
  }

  return (
    <div className="applicants-list">
      <button className="btn-ghost back-btn" onClick={onBack}>← Back to jobs</button>
      <h3>{job.title} — applicants</h3>
      {loading ? (
        <div className="muted">Loading…</div>
      ) : applicants?.length === 0 ? (
        <div className="empty-state muted">No applicants yet.</div>
      ) : (
        <div className="applicant-table">
          {applicants.map((a) => (
            <div key={a.application_id} className="applicant-row card"
              onClick={() => setSelectedApp(a.application_id)}>
              <div className="applicant-info">
                <strong>{a.candidate_name}</strong>
                <span className="muted">{a.candidate_email}</span>
                <span className={`status-badge status-${a.status}`}>{a.status}</span>
              </div>
              {a.score ? (
                <div className="score-row compact">
                  <div className="score-badge sm" style={{ background: bandColor(a.score.band) }}>
                    {a.score.overall_score}
                  </div>
                  <span className="muted">{a.score.band?.replace(/_/g, " ")}</span>
                </div>
              ) : (
                <span className="muted">No score yet</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function EmployerDashboard({ user, token, onLogout }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState(null);
  const [showNewJob, setShowNewJob] = useState(false);

  async function loadJobs() {
    setLoading(true);
    listEmployerJobs(token).then(setJobs).finally(() => setLoading(false));
  }

  useEffect(() => { loadJobs(); }, []);

  async function toggleJob(job) {
    await updateJob(job.job_id, { is_active: !job.is_active }, token);
    loadJobs();
  }

  if (selectedJob) {
    return <ApplicantsList job={selectedJob} token={token} onBack={() => setSelectedJob(null)} />;
  }

  return (
    <div className="employer-dashboard">
      <div className="dashboard-header">
        <div>
          <h2>{user.company_name}</h2>
          <span className="muted">{user.email}</span>
        </div>
        <button className="btn-ghost" onClick={onLogout}>Logout</button>
      </div>

      {showNewJob ? (
        <NewJobForm token={token} onCreated={() => { setShowNewJob(false); loadJobs(); }} />
      ) : (
        <button onClick={() => setShowNewJob(true)} style={{ marginBottom: "1.5rem" }}>
          + Post new opening
        </button>
      )}

      <h3>Your openings</h3>
      {loading ? (
        <div className="muted">Loading…</div>
      ) : jobs.length === 0 ? (
        <div className="empty-state muted">No job postings yet. Create your first opening above.</div>
      ) : (
        <div className="job-list">
          {jobs.map((job) => (
            <div key={job.job_id} className="job-card">
              <div className="job-card-body">
                <h3>{job.title}</h3>
                <div className="job-meta">
                  <span className="tag">{job.employment_type}</span>
                  <span className="tag">{job.location}</span>
                  <span className={`tag ${job.is_active ? "tag-green" : "tag-gray"}`}>
                    {job.is_active ? "Active" : "Closed"}
                  </span>
                  <span className="muted">{job.application_count} applicants</span>
                </div>
              </div>
              <div className="job-card-actions">
                <button className="btn-secondary" onClick={() => setSelectedJob(job)}>
                  View applicants
                </button>
                <button className="btn-ghost" onClick={() => toggleJob(job)}>
                  {job.is_active ? "Close" : "Reopen"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
