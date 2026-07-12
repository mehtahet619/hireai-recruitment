import React, { useEffect, useState } from "react";
import { listEmployerJobs, createJob, updateJob, getJobApplicants, getApplicant, getOnboardingPlans, completeOnboardingTask, listCompensation, createCompensation, initiatePayrollRun, listPayrollRuns, getRunPayslips } from "./api.js";

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function daysSince(hireDateStr) {
  const hire = new Date(hireDateStr);
  const today = new Date();
  // Zero out time parts for a clean date diff
  hire.setHours(0, 0, 0, 0);
  today.setHours(0, 0, 0, 0);
  return Math.max(0, Math.floor((today - hire) / (1000 * 60 * 60 * 24)));
}

function isTaskOverdue(task, hireDateStr) {
  if (task.completed_at) return false;
  const hire = new Date(hireDateStr);
  const dueDate = new Date(hire);
  dueDate.setDate(dueDate.getDate() + task.due_offset_days);
  dueDate.setHours(0, 0, 0, 0);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return dueDate < today;
}

// ---------------------------------------------------------------------------
// OnboardingTab
// ---------------------------------------------------------------------------

function OnboardingTab({ token }) {
  const [plans, setPlans] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedPlan, setExpandedPlan] = useState(null);
  const [completing, setCompleting] = useState(null); // "planId:taskId"

  async function loadPlans() {
    setLoading(true);
    setError("");
    try {
      const data = await getOnboardingPlans(token);
      setPlans(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadPlans(); }, []);

  async function handleCompleteTask(planId, taskId) {
    const key = `${planId}:${taskId}`;
    setCompleting(key);
    try {
      await completeOnboardingTask(planId, taskId, token);
      await loadPlans();
    } catch (e) {
      setError(e.message);
    } finally {
      setCompleting(null);
    }
  }

  if (loading) return <div className="muted">Loading onboarding plans…</div>;
  if (error) return <div className="error">{error}</div>;
  if (!plans || plans.length === 0) {
    return (
      <div className="empty-state muted">
        No onboarding plans yet. Plans are created when an application is moved to "hired".
      </div>
    );
  }

  return (
    <div className="onboarding-tab">
      <h3 style={{ marginBottom: "1rem" }}>Engineer Onboarding</h3>
      <div className="job-list">
        {plans.map((plan) => {
          const totalTasks = plan.tasks.length;
          const completedTasks = plan.tasks.filter((t) => t.completed_at).length;
          const overdueTasks = plan.tasks.filter((t) => isTaskOverdue(t, plan.hire_date));
          const pendingTasks = plan.tasks.filter(
            (t) => !t.completed_at && !isTaskOverdue(t, plan.hire_date)
          );
          const days = daysSince(plan.hire_date);
          const isExpanded = expandedPlan === plan.plan_id;
          const progressPct = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0;

          return (
            <div key={plan.plan_id} className="card" style={{ marginBottom: "12px" }}>
              {/* Plan summary row */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  cursor: "pointer",
                  gap: "16px",
                }}
                onClick={() => setExpandedPlan(isExpanded ? null : plan.plan_id)}
              >
                <div>
                  <strong style={{ fontSize: "15px" }}>Engineer: {plan.engineer_id}</strong>
                  <div className="muted" style={{ marginTop: "4px" }}>
                    Hired {plan.hire_date} &mdash; {days} day{days !== 1 ? "s" : ""} ago
                  </div>
                  <div style={{ marginTop: "8px", display: "flex", gap: "12px", flexWrap: "wrap" }}>
                    <span className="tag tag-green">
                      ✓ {completedTasks} completed
                    </span>
                    <span className="tag">
                      ⏳ {pendingTasks.length} pending
                    </span>
                    {overdueTasks.length > 0 && (
                      <span className="tag" style={{ background: "#ffebe9", color: "#d1242f" }}>
                        ⚠ {overdueTasks.length} overdue
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ textAlign: "right", flexShrink: 0 }}>
                  <div style={{ fontSize: "13px", fontWeight: 600 }}>
                    {progressPct}%
                  </div>
                  <div
                    style={{
                      width: "80px",
                      height: "6px",
                      background: "#eaeef2",
                      borderRadius: "999px",
                      marginTop: "4px",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${progressPct}%`,
                        height: "100%",
                        background: progressPct === 100 ? "#2da44e" : "#1f6feb",
                        borderRadius: "999px",
                        transition: "width 0.3s",
                      }}
                    />
                  </div>
                  <div className="muted" style={{ marginTop: "4px" }}>
                    {completedTasks}/{totalTasks} tasks
                  </div>
                  <div className="muted" style={{ marginTop: "6px", fontSize: "12px" }}>
                    {isExpanded ? "▲ hide" : "▼ show"} tasks
                  </div>
                </div>
              </div>

              {/* Expanded task list */}
              {isExpanded && (
                <div style={{ marginTop: "16px", borderTop: "1px solid #eaeef2", paddingTop: "12px" }}>
                  {plan.tasks.length === 0 ? (
                    <div className="muted">No tasks in this plan.</div>
                  ) : (
                    <table>
                      <thead>
                        <tr>
                          <th>Task</th>
                          <th>Role</th>
                          <th>Due (day)</th>
                          <th>Status</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {plan.tasks.map((task) => {
                          const overdue = isTaskOverdue(task, plan.hire_date);
                          const done = !!task.completed_at;
                          const key = `${plan.plan_id}:${task.task_id}`;
                          const isCompleting = completing === key;
                          return (
                            <tr key={task.task_id}>
                              <td>
                                <div style={{ fontWeight: 500 }}>{task.title}</div>
                                {task.description && (
                                  <div className="muted" style={{ fontSize: "12px" }}>
                                    {task.description}
                                  </div>
                                )}
                              </td>
                              <td className="muted">{task.assigned_role || "—"}</td>
                              <td className="muted">Day {task.due_offset_days}</td>
                              <td>
                                {done ? (
                                  <span className="tag tag-green">✓ Done</span>
                                ) : overdue ? (
                                  <span
                                    className="tag"
                                    style={{ background: "#ffebe9", color: "#d1242f", fontWeight: 700 }}
                                  >
                                    Overdue
                                  </span>
                                ) : (
                                  <span className="tag">Pending</span>
                                )}
                              </td>
                              <td>
                                {!done && (
                                  <button
                                    className="btn-secondary"
                                    style={{ padding: "4px 10px", fontSize: "12px" }}
                                    disabled={isCompleting}
                                    onClick={() => handleCompleteTask(plan.plan_id, task.task_id)}
                                  >
                                    {isCompleting ? "…" : "Mark done"}
                                  </button>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PayrollTab
// ---------------------------------------------------------------------------

function PayrollTab({ token }) {
  const [compensation, setCompensation] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [runLoading, setRunLoading] = useState(false);
  const [selectedRun, setSelectedRun] = useState(null);
  const [payslips, setPayslips] = useState([]);
  const [showCompForm, setShowCompForm] = useState(false);
  const [compForm, setCompForm] = useState({
    engineer_id: "", base_salary: "", currency: "USD",
    pay_frequency: "monthly", effective_date: "", deductions: "[]",
  });
  const [savingComp, setSavingComp] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [comp, runsData] = await Promise.all([
        listCompensation(token),
        listPayrollRuns(token),
      ]);
      setCompensation(comp);
      setRuns(runsData);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleInitiateRun() {
    setRunLoading(true);
    setError("");
    try {
      await initiatePayrollRun(token);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setRunLoading(false);
    }
  }

  async function handleSelectRun(runId) {
    if (selectedRun === runId) { setSelectedRun(null); setPayslips([]); return; }
    setSelectedRun(runId);
    try {
      const data = await getRunPayslips(runId, token);
      setPayslips(data);
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleSaveComp(e) {
    e.preventDefault();
    setSavingComp(true);
    setError("");
    try {
      let deductions = [];
      try { deductions = JSON.parse(compForm.deductions || "[]"); } catch (_) {}
      await createCompensation({
        engineer_id: compForm.engineer_id,
        base_salary: parseFloat(compForm.base_salary),
        currency: compForm.currency,
        pay_frequency: compForm.pay_frequency,
        effective_date: compForm.effective_date,
        deductions,
      }, token);
      setShowCompForm(false);
      setCompForm({ engineer_id: "", base_salary: "", currency: "USD", pay_frequency: "monthly", effective_date: "", deductions: "[]" });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingComp(false);
    }
  }

  if (loading) return <div className="muted">Loading payroll data…</div>;

  return (
    <div>
      {error && <div className="error" style={{ marginBottom: "1rem" }}>{error}</div>}

      {/* Compensation Records */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <h3 style={{ margin: 0 }}>Compensation Records</h3>
        <button className="btn-secondary" onClick={() => setShowCompForm(!showCompForm)}>
          {showCompForm ? "Cancel" : "+ Add Record"}
        </button>
      </div>

      {showCompForm && (
        <form className="card" onSubmit={handleSaveComp} style={{ marginBottom: "1rem" }}>
          <div className="form-row">
            <div>
              <label>Engineer ID</label>
              <input value={compForm.engineer_id} required
                onChange={e => setCompForm({ ...compForm, engineer_id: e.target.value })} />
            </div>
            <div>
              <label>Base Salary</label>
              <input type="number" value={compForm.base_salary} required min="0.01"
                onChange={e => setCompForm({ ...compForm, base_salary: e.target.value })} />
            </div>
          </div>
          <div className="form-row">
            <div>
              <label>Currency</label>
              <input value={compForm.currency} required
                onChange={e => setCompForm({ ...compForm, currency: e.target.value })} />
            </div>
            <div>
              <label>Pay Frequency</label>
              <select value={compForm.pay_frequency} onChange={e => setCompForm({ ...compForm, pay_frequency: e.target.value })}>
                <option value="monthly">Monthly</option>
                <option value="bi-weekly">Bi-weekly</option>
                <option value="weekly">Weekly</option>
              </select>
            </div>
            <div>
              <label>Effective Date</label>
              <input type="date" value={compForm.effective_date} required
                onChange={e => setCompForm({ ...compForm, effective_date: e.target.value })} />
            </div>
          </div>
          <label>Deductions (JSON array)</label>
          <textarea rows={2} value={compForm.deductions}
            placeholder='[{"name":"Tax","type":"tax","pct":20}]'
            onChange={e => setCompForm({ ...compForm, deductions: e.target.value })} />
          <button type="submit" disabled={savingComp}>{savingComp ? "Saving…" : "Save"}</button>
        </form>
      )}

      {compensation.length === 0 ? (
        <div className="empty-state muted" style={{ marginBottom: "1.5rem" }}>No compensation records yet.</div>
      ) : (
        <div className="card" style={{ marginBottom: "1.5rem", padding: "0" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #eaeef2" }}>
                <th style={{ padding: "8px 12px", textAlign: "left" }}>Engineer</th>
                <th style={{ padding: "8px 12px", textAlign: "right" }}>Salary</th>
                <th style={{ padding: "8px 12px" }}>Currency</th>
                <th style={{ padding: "8px 12px" }}>Frequency</th>
                <th style={{ padding: "8px 12px" }}>Effective</th>
              </tr>
            </thead>
            <tbody>
              {compensation.map((r) => (
                <tr key={r.record_id} style={{ borderBottom: "1px solid #f0f3f6" }}>
                  <td style={{ padding: "8px 12px" }}>{r.engineer_id}</td>
                  <td style={{ padding: "8px 12px", textAlign: "right" }}>{r.base_salary?.toLocaleString()}</td>
                  <td style={{ padding: "8px 12px" }}>{r.currency}</td>
                  <td style={{ padding: "8px 12px" }}>{r.pay_frequency}</td>
                  <td style={{ padding: "8px 12px" }} className="muted">{r.effective_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Payroll Runs */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <h3 style={{ margin: 0 }}>Payroll Runs</h3>
        <button onClick={handleInitiateRun} disabled={runLoading}>
          {runLoading ? "Running…" : "▶ Run Payroll"}
        </button>
      </div>

      {runs.length === 0 ? (
        <div className="empty-state muted">No payroll runs yet.</div>
      ) : (
        <div className="job-list">
          {runs.map((run) => (
            <div key={run.run_id}>
              <div className="card" style={{ cursor: "pointer", marginBottom: "4px" }}
                onClick={() => handleSelectRun(run.run_id)}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <span className={`tag ${run.status === "completed" ? "tag-green" : run.status === "failed" ? "" : ""}`}
                      style={run.status === "failed" ? { background: "#ffebe9", color: "#d1242f" } : {}}>
                      {run.status}
                    </span>
                    <span className="muted" style={{ marginLeft: "8px", fontSize: "13px" }}>
                      {new Date(run.initiated_at).toLocaleString()}
                    </span>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <strong>{run.total_gross?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
                    <span className="muted" style={{ marginLeft: "8px" }}>{run.payslip_count} payslips</span>
                  </div>
                </div>
              </div>
              {selectedRun === run.run_id && payslips.length > 0 && (
                <div className="card" style={{ marginBottom: "8px", background: "#f6f8fa" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr>
                        <th style={{ padding: "6px 10px", textAlign: "left" }}>Engineer</th>
                        <th style={{ padding: "6px 10px", textAlign: "right" }}>Gross</th>
                        <th style={{ padding: "6px 10px", textAlign: "right" }}>Net</th>
                        <th style={{ padding: "6px 10px" }}>Currency</th>
                        <th style={{ padding: "6px 10px" }}>Period</th>
                      </tr>
                    </thead>
                    <tbody>
                      {payslips.map((ps) => (
                        <tr key={ps.payslip_id} style={{ borderTop: "1px solid #eaeef2" }}>
                          <td style={{ padding: "6px 10px" }}>{ps.engineer_id}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right" }}>{ps.gross_pay?.toFixed(2)}</td>
                          <td style={{ padding: "6px 10px", textAlign: "right" }}>{ps.net_pay?.toFixed(2)}</td>
                          <td style={{ padding: "6px 10px" }}>{ps.currency}</td>
                          <td style={{ padding: "6px 10px" }} className="muted">{ps.period_start} → {ps.period_end}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function JobsTab({ token, onUpgrade }) {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState(null);
  const [showNewJob, setShowNewJob] = useState(false);
  const [plan, setPlan] = useState(null);

  async function loadJobs() {
    setLoading(true);
    listEmployerJobs(token).then(setJobs).finally(() => setLoading(false));
  }

  async function loadPlan() {
    try {
      const BASE = import.meta.env.VITE_API_BASE || "";
      const res = await fetch(`${BASE}/api/employer/plan`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setPlan(await res.json());
    } catch (_) {}
  }

  useEffect(() => { loadJobs(); loadPlan(); }, []);

  async function toggleJob(job) {
    await updateJob(job.job_id, { is_active: !job.is_active }, token);
    loadJobs();
  }

  async function handleNewJobClick() {
    if (plan && plan.plan === "free") {
      onUpgrade && onUpgrade();
      return;
    }
    setShowNewJob(true);
  }

  if (selectedJob) {
    return <ApplicantsList job={selectedJob} token={token} onBack={() => setSelectedJob(null)} />;
  }

  return (
    <>
      {showNewJob ? (
        <NewJobForm token={token} onCreated={() => { setShowNewJob(false); loadJobs(); }} />
      ) : (
        <button onClick={handleNewJobClick} style={{ marginBottom: "1.5rem" }}>
          + Post new opening
        </button>
      )}

      {plan && plan.plan === "free" && (
        <div className="upgrade-banner">
          <span>🔒 You're on the free plan — upgrade to post jobs</span>
          <button onClick={() => onUpgrade && onUpgrade()}>View plans</button>
        </div>
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
    </>
  );
}

const TABS = ["Jobs", "Onboarding", "Payroll"];

export default function EmployerDashboard({ user, token, onLogout, onUpgrade }) {
  const [activeTab, setActiveTab] = useState("Jobs");

  return (
    <div className="employer-dashboard">
      <div className="dashboard-header">
        <div>
          <h2>{user.company_name}</h2>
          <span className="muted">{user.email}</span>
        </div>
        <button className="btn-ghost" onClick={onLogout}>Logout</button>
      </div>

      <div className="tabs">
        {TABS.map((tab) => (
          <button
            key={tab}
            className={activeTab === tab ? "active" : ""}
            onClick={() => setActiveTab(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === "Jobs" && <JobsTab token={token} onUpgrade={onUpgrade} />}
      {activeTab === "Onboarding" && <OnboardingTab token={token} />}
      {activeTab === "Payroll" && <PayrollTab token={token} />}
    </div>
  );
}
