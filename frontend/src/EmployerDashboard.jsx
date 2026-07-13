import React, { useEffect, useState } from "react";
import { listEmployerJobs, createJob, updateJob, getJobApplicants, getApplicant, getOnboardingPlans, completeOnboardingTask, listCompensation, createCompensation, initiatePayrollRun, listPayrollRuns, getRunPayslips, listPerformanceCycles, createPerformanceCycle, activatePerformanceCycle, getPerformanceCycleResults, listComplianceRules, createComplianceRule, seedComplianceTemplates, listComplianceAlerts, resolveComplianceAlert, listIntegrations, createIntegration, validateIntegration, updateIntegration, getAnalyticsReport, getAnalyticsAnomalies, getAnalyticsBenchmarks } from "./api.js";

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

// ---------------------------------------------------------------------------
// AnalyticsTab
// ---------------------------------------------------------------------------

const REPORT_TYPES = [
  { key: "hiring_funnel", label: "Hiring Funnel" },
  { key: "time_to_hire", label: "Time to Hire" },
  { key: "onboarding_completion", label: "Onboarding Completion" },
  { key: "performance_distributions", label: "Performance Scores" },
  { key: "attrition_risk", label: "Attrition Risk" },
  { key: "team_composition", label: "Team Composition" },
];

const BASE = import.meta.env.VITE_API_BASE || "";

function AnalyticsTab({ token }) {
  const [activeReport, setActiveReport] = useState("hiring_funnel");
  const [reportData, setReportData] = useState(null);
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadReport(type) {
    setActiveReport(type);
    setLoading(true);
    setError("");
    try {
      const [data, anom] = await Promise.all([
        getAnalyticsReport(type, token),
        getAnalyticsAnomalies(token),
      ]);
      setReportData(data);
      setAnomalies(anom);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadReport("hiring_funnel"); }, []);

  function handleExport(fmt) {
    const url = `${BASE}/api/employer/analytics/${activeReport}/export?fmt=${fmt}`;
    const a = document.createElement("a");
    a.href = url;
    a.download = `${activeReport}.${fmt}`;
    // add auth header via fetch then blob download
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.blob())
      .then(blob => {
        const objUrl = URL.createObjectURL(blob);
        a.href = objUrl;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(objUrl);
      })
      .catch(e => setError(e.message));
  }

  function renderMetric(key, value) {
    if (typeof value === "number") {
      const display = Number.isInteger(value) ? value : (value * 100).toFixed(1) + (key.includes("rate") || key.includes("pct") ? "%" : "");
      return <div key={key} className="card" style={{ padding: "12px 16px", flex: "1", minWidth: "120px" }}>
        <div className="muted" style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.5px" }}>{key.replace(/_/g, " ")}</div>
        <div style={{ fontSize: "24px", fontWeight: 700, marginTop: "4px" }}>{display}</div>
      </div>;
    }
    if (typeof value === "object" && value !== null) {
      return <div key={key} className="card" style={{ padding: "12px 16px", flex: "1", minWidth: "160px" }}>
        <div className="muted" style={{ fontSize: "11px", textTransform: "uppercase" }}>{key.replace(/_/g, " ")}</div>
        {Object.entries(value).map(([k, v]) => (
          <div key={k} style={{ fontSize: "13px", marginTop: "4px" }}>
            <span className="muted">{k}: </span><strong>{v}</strong>
          </div>
        ))}
      </div>;
    }
    return null;
  }

  return (
    <div>
      {error && <div className="error" style={{ marginBottom: "1rem" }}>{error}</div>}

      {/* Anomaly alert panel */}
      {anomalies.length > 0 && (
        <div style={{ background: "#fff8c5", border: "1px solid #d4a72c", borderRadius: "8px", padding: "10px 14px", marginBottom: "1rem" }}>
          <strong>⚠ {anomalies.length} anomaly alert{anomalies.length !== 1 ? "s" : ""} detected</strong>
          {anomalies.map((a, i) => (
            <div key={i} className="muted" style={{ fontSize: "12px", marginTop: "4px" }}>{a.message}</div>
          ))}
        </div>
      )}

      {/* Report selector */}
      <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "1rem" }}>
        {REPORT_TYPES.map(r => (
          <button key={r.key}
            className={activeReport === r.key ? "" : "btn-secondary"}
            style={{ padding: "6px 12px", fontSize: "13px" }}
            onClick={() => loadReport(r.key)}>
            {r.label}
          </button>
        ))}
      </div>

      {/* Export buttons */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "1rem" }}>
        <button className="btn-ghost" style={{ fontSize: "12px" }} onClick={() => handleExport("json")}>↓ JSON</button>
        <button className="btn-ghost" style={{ fontSize: "12px" }} onClick={() => handleExport("csv")}>↓ CSV</button>
      </div>

      {/* Report data */}
      {loading ? (
        <div className="muted">Loading report…</div>
      ) : reportData ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "12px" }}>
          {Object.entries(reportData).map(([k, v]) => renderMetric(k, v))}
        </div>
      ) : (
        <div className="empty-state muted">No data available.</div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// IntegrationsTab
// ---------------------------------------------------------------------------

function IntegrationsTab({ token }) {
  const [connectors, setConnectors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [validating, setValidating] = useState(null);
  const [toggling, setToggling] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ connector_type: "github", token: "", api_token: "", base_url: "", bot_token: "", webhook_secret: "" });
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      setConnectors(await listIntegrations(token));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const configMap = {
        github: { token: form.token },
        jira: { api_token: form.api_token, base_url: form.base_url },
        slack: { bot_token: form.bot_token },
        hris_webhook: { webhook_secret: form.webhook_secret },
      };
      await createIntegration({ connector_type: form.connector_type, config: configMap[form.connector_type] || {} }, token);
      setShowForm(false);
      setForm({ connector_type: "github", token: "", api_token: "", base_url: "", bot_token: "", webhook_secret: "" });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleValidate(connectorId) {
    setValidating(connectorId);
    setError("");
    try {
      await validateIntegration(connectorId, token);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setValidating(null);
    }
  }

  async function handleToggle(connector) {
    setToggling(connector.connector_id);
    setError("");
    try {
      const newStatus = connector.status === "disabled" ? "active" : "disabled";
      await updateIntegration(connector.connector_id, { status: newStatus }, token);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setToggling(null);
    }
  }

  function statusColor(status) {
    return status === "active" ? "#2da44e" : status === "degraded" ? "#d1242f" : "#57606a";
  }

  const CONNECTOR_TYPES = ["github", "jira", "slack", "hris_webhook"];

  if (loading) return <div className="muted">Loading integrations…</div>;

  return (
    <div>
      {error && <div className="error" style={{ marginBottom: "1rem" }}>{error}</div>}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <h3 style={{ margin: 0 }}>Integration Connectors</h3>
        <button className="btn-secondary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "+ Add Connector"}
        </button>
      </div>

      {showForm && (
        <form className="card" onSubmit={handleCreate} style={{ marginBottom: "1rem" }}>
          <div className="form-row">
            <div>
              <label>Connector Type</label>
              <select value={form.connector_type} onChange={e => setForm({ ...form, connector_type: e.target.value })}>
                {CONNECTOR_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
          {form.connector_type === "github" && (
            <div><label>GitHub Token</label><input type="password" value={form.token} onChange={e => setForm({ ...form, token: e.target.value })} placeholder="ghp_..." /></div>
          )}
          {form.connector_type === "jira" && (<>
            <div><label>Jira Base URL</label><input value={form.base_url} onChange={e => setForm({ ...form, base_url: e.target.value })} placeholder="https://company.atlassian.net" /></div>
            <div><label>API Token</label><input type="password" value={form.api_token} onChange={e => setForm({ ...form, api_token: e.target.value })} /></div>
          </>)}
          {form.connector_type === "slack" && (
            <div><label>Bot Token</label><input type="password" value={form.bot_token} onChange={e => setForm({ ...form, bot_token: e.target.value })} placeholder="xoxb-..." /></div>
          )}
          {form.connector_type === "hris_webhook" && (
            <div><label>Webhook Secret</label><input type="password" value={form.webhook_secret} onChange={e => setForm({ ...form, webhook_secret: e.target.value })} /></div>
          )}
          <button type="submit" disabled={saving}>{saving ? "Saving…" : "Add Connector"}</button>
        </form>
      )}

      {connectors.length === 0 ? (
        <div className="empty-state muted">No connectors yet. Add one to start collecting signals from your engineering tools.</div>
      ) : (
        <div className="job-list">
          {connectors.map(c => (
            <div key={c.connector_id} className="card" style={{ marginBottom: "8px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <strong style={{ textTransform: "capitalize" }}>{c.connector_type.replace("_", " ")}</strong>
                  <div style={{ display: "flex", gap: "8px", marginTop: "6px", flexWrap: "wrap" }}>
                    <span className="tag" style={{ color: statusColor(c.status), fontWeight: 600 }}>
                      ● {c.status}
                    </span>
                    {c.last_sync_at && (
                      <span className="muted" style={{ fontSize: "12px" }}>
                        Last sync: {new Date(c.last_sync_at).toLocaleString()}
                      </span>
                    )}
                    {c.error_count > 0 && (
                      <span className="tag" style={{ background: "#ffebe9", color: "#d1242f", fontSize: "11px" }}>
                        {c.error_count} error{c.error_count !== 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ display: "flex", gap: "8px", flexShrink: 0 }}>
                  <button className="btn-secondary" style={{ padding: "4px 10px", fontSize: "12px" }}
                    disabled={validating === c.connector_id}
                    onClick={() => handleValidate(c.connector_id)}>
                    {validating === c.connector_id ? "…" : "Validate"}
                  </button>
                  <button className="btn-ghost" style={{ padding: "4px 10px", fontSize: "12px" }}
                    disabled={toggling === c.connector_id}
                    onClick={() => handleToggle(c)}>
                    {toggling === c.connector_id ? "…" : c.status === "disabled" ? "Enable" : "Disable"}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ComplianceTab
// ---------------------------------------------------------------------------

function ComplianceTab({ token }) {
  const [alerts, setAlerts] = useState([]);
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [resolving, setResolving] = useState(null);
  const [seeding, setSeeding] = useState(false);
  const [showRules, setShowRules] = useState(false);
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [ruleForm, setRuleForm] = useState({
    name: "", jurisdiction: "US_federal", category: "working_hours",
    field: "weekly_hours", op: "gt", threshold: "48", severity: "warning",
  });
  const [savingRule, setSavingRule] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [alertsData, rulesData] = await Promise.all([
        listComplianceAlerts(token),
        listComplianceRules(token),
      ]);
      setAlerts(alertsData);
      setRules(rulesData);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleResolve(alertId) {
    setResolving(alertId);
    setError("");
    try {
      await resolveComplianceAlert(alertId, "employer", token);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setResolving(null);
    }
  }

  async function handleSeedTemplates() {
    setSeeding(true);
    setError("");
    try {
      await seedComplianceTemplates(token);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSeeding(false);
    }
  }

  async function handleCreateRule(e) {
    e.preventDefault();
    setSavingRule(true);
    setError("");
    try {
      await createComplianceRule({
        name: ruleForm.name,
        jurisdiction: ruleForm.jurisdiction,
        category: ruleForm.category,
        trigger_condition: { field: ruleForm.field, op: ruleForm.op, threshold: parseFloat(ruleForm.threshold) },
        severity: ruleForm.severity,
        notification_recipients: [],
      }, token);
      setShowRuleForm(false);
      setRuleForm({ name: "", jurisdiction: "US_federal", category: "working_hours", field: "weekly_hours", op: "gt", threshold: "48", severity: "warning" });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingRule(false);
    }
  }

  function severityStyle(sev) {
    return sev === "critical" ? { background: "#ffebe9", color: "#d1242f" }
         : sev === "warning"  ? { background: "#fff8c5", color: "#9a6700" }
         : { background: "#ddf4ff", color: "#0550ae" };
  }

  const openAlerts = alerts.filter(a => a.status === "open");
  const resolvedAlerts = alerts.filter(a => a.status === "resolved");

  if (loading) return <div className="muted">Loading compliance data…</div>;

  return (
    <div>
      {error && <div className="error" style={{ marginBottom: "1rem" }}>{error}</div>}

      {/* Open alerts — prominently surfaced */}
      {openAlerts.length > 0 && (
        <div style={{ background: "#ffebe9", border: "1px solid #ffcecb", borderRadius: "8px", padding: "12px 16px", marginBottom: "1.5rem" }}>
          <strong style={{ color: "#d1242f" }}>⚠ {openAlerts.length} open compliance alert{openAlerts.length !== 1 ? "s" : ""} require attention</strong>
        </div>
      )}

      {/* Alerts section */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <h3 style={{ margin: 0 }}>Compliance Alerts</h3>
      </div>

      {alerts.length === 0 ? (
        <div className="empty-state muted" style={{ marginBottom: "1.5rem" }}>No compliance alerts. Configure rules and run an evaluation to detect violations.</div>
      ) : (
        <div style={{ marginBottom: "1.5rem" }}>
          {openAlerts.map(alert => (
            <div key={alert.alert_id} className="card" style={{ marginBottom: "8px", borderLeft: "4px solid #d1242f" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <span className="tag" style={severityStyle(alert.severity)}>{alert.severity}</span>
                  <span className="muted" style={{ marginLeft: "8px", fontSize: "12px" }}>
                    {new Date(alert.created_at).toLocaleString()}
                  </span>
                  <div style={{ marginTop: "6px", fontSize: "13px" }}>{alert.recommended_action}</div>
                  <div className="muted" style={{ fontSize: "11px", marginTop: "4px" }}>Engineer: {alert.pseudonymous_engineer_id.slice(0, 8)}…</div>
                </div>
                <button className="btn-secondary" style={{ padding: "4px 10px", fontSize: "12px", flexShrink: 0 }}
                  disabled={resolving === alert.alert_id}
                  onClick={() => handleResolve(alert.alert_id)}>
                  {resolving === alert.alert_id ? "…" : "Resolve"}
                </button>
              </div>
            </div>
          ))}
          {resolvedAlerts.length > 0 && (
            <div className="muted" style={{ fontSize: "12px", marginTop: "8px" }}>
              + {resolvedAlerts.length} resolved alert{resolvedAlerts.length !== 1 ? "s" : ""}
            </div>
          )}
        </div>
      )}

      {/* Rules section */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <h3 style={{ margin: 0 }}>Compliance Rules</h3>
        <div style={{ display: "flex", gap: "8px" }}>
          <button className="btn-secondary" style={{ fontSize: "12px", padding: "4px 10px" }}
            disabled={seeding} onClick={handleSeedTemplates}>
            {seeding ? "Seeding…" : "Seed Templates"}
          </button>
          <button className="btn-secondary" onClick={() => setShowRuleForm(!showRuleForm)}>
            {showRuleForm ? "Cancel" : "+ Add Rule"}
          </button>
          <button className="btn-ghost" style={{ fontSize: "12px" }} onClick={() => setShowRules(!showRules)}>
            {showRules ? "Hide rules" : `Show ${rules.length} rules`}
          </button>
        </div>
      </div>

      {showRuleForm && (
        <form className="card" onSubmit={handleCreateRule} style={{ marginBottom: "1rem" }}>
          <div className="form-row">
            <div>
              <label>Rule Name</label>
              <input value={ruleForm.name} required onChange={e => setRuleForm({ ...ruleForm, name: e.target.value })} />
            </div>
            <div>
              <label>Jurisdiction</label>
              <select value={ruleForm.jurisdiction} onChange={e => setRuleForm({ ...ruleForm, jurisdiction: e.target.value })}>
                <option value="US_federal">US Federal</option>
                <option value="UK">UK</option>
                <option value="India">India</option>
              </select>
            </div>
          </div>
          <div className="form-row">
            <div>
              <label>Category</label>
              <select value={ruleForm.category} onChange={e => setRuleForm({ ...ruleForm, category: e.target.value })}>
                <option value="working_hours">Working Hours</option>
                <option value="leave">Leave</option>
                <option value="data_privacy">Data Privacy</option>
                <option value="pay_equity">Pay Equity</option>
              </select>
            </div>
            <div>
              <label>Severity</label>
              <select value={ruleForm.severity} onChange={e => setRuleForm({ ...ruleForm, severity: e.target.value })}>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>
          <div className="form-row">
            <div><label>Field</label><input value={ruleForm.field} onChange={e => setRuleForm({ ...ruleForm, field: e.target.value })} /></div>
            <div>
              <label>Operator</label>
              <select value={ruleForm.op} onChange={e => setRuleForm({ ...ruleForm, op: e.target.value })}>
                <option value="gt">&gt;</option><option value="gte">&gt;=</option>
                <option value="lt">&lt;</option><option value="lte">&lt;=</option>
                <option value="eq">=</option>
              </select>
            </div>
            <div><label>Threshold</label><input type="number" value={ruleForm.threshold} onChange={e => setRuleForm({ ...ruleForm, threshold: e.target.value })} /></div>
          </div>
          <button type="submit" disabled={savingRule}>{savingRule ? "Saving…" : "Save Rule"}</button>
        </form>
      )}

      {showRules && rules.length > 0 && (
        <div className="card" style={{ padding: 0 }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #eaeef2" }}>
                <th style={{ padding: "8px 12px", textAlign: "left" }}>Rule</th>
                <th style={{ padding: "8px 12px" }}>Jurisdiction</th>
                <th style={{ padding: "8px 12px" }}>Category</th>
                <th style={{ padding: "8px 12px" }}>Severity</th>
              </tr>
            </thead>
            <tbody>
              {rules.map(r => (
                <tr key={r.rule_id} style={{ borderBottom: "1px solid #f0f3f6" }}>
                  <td style={{ padding: "8px 12px" }}>{r.name}</td>
                  <td style={{ padding: "8px 12px" }} className="muted">{r.jurisdiction}</td>
                  <td style={{ padding: "8px 12px" }} className="muted">{r.category}</td>
                  <td style={{ padding: "8px 12px" }}><span className="tag" style={severityStyle(r.severity)}>{r.severity}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PerformanceTab
// ---------------------------------------------------------------------------

function PerformanceTab({ token }) {
  const [cycles, setCycles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedCycle, setSelectedCycle] = useState(null);
  const [results, setResults] = useState(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [showNewCycle, setShowNewCycle] = useState(false);
  const [activating, setActivating] = useState(null);
  const [cycleForm, setCycleForm] = useState({
    name: "", start_date: "", end_date: "",
  });
  const [savingCycle, setSavingCycle] = useState(false);

  async function loadCycles() {
    setLoading(true);
    setError("");
    try {
      const data = await listPerformanceCycles(token);
      setCycles(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadCycles(); }, []);

  async function handleSelectCycle(cycleId) {
    if (selectedCycle === cycleId) { setSelectedCycle(null); setResults(null); return; }
    setSelectedCycle(cycleId);
    setResultsLoading(true);
    try {
      const data = await getPerformanceCycleResults(cycleId, token);
      setResults(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setResultsLoading(false);
    }
  }

  async function handleActivate(cycleId) {
    setActivating(cycleId);
    setError("");
    try {
      await activatePerformanceCycle(cycleId, token);
      await loadCycles();
    } catch (e) {
      setError(e.message);
    } finally {
      setActivating(null);
    }
  }

  async function handleCreateCycle(e) {
    e.preventDefault();
    setSavingCycle(true);
    setError("");
    try {
      await createPerformanceCycle({
        name: cycleForm.name,
        start_date: cycleForm.start_date,
        end_date: cycleForm.end_date,
        participant_ids: [],
        review_template: {},
      }, token);
      setShowNewCycle(false);
      setCycleForm({ name: "", start_date: "", end_date: "" });
      await loadCycles();
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingCycle(false);
    }
  }

  function scoreColor(score) {
    if (score >= 0.75) return "#2da44e";
    if (score >= 0.5) return "#bf8700";
    return "#d1242f";
  }

  if (loading) return <div className="muted">Loading performance cycles…</div>;

  return (
    <div>
      {error && <div className="error" style={{ marginBottom: "1rem" }}>{error}</div>}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
        <h3 style={{ margin: 0 }}>Performance Cycles</h3>
        <button className="btn-secondary" onClick={() => setShowNewCycle(!showNewCycle)}>
          {showNewCycle ? "Cancel" : "+ New Cycle"}
        </button>
      </div>

      {showNewCycle && (
        <form className="card" onSubmit={handleCreateCycle} style={{ marginBottom: "1rem" }}>
          <div className="form-row">
            <div>
              <label>Cycle Name</label>
              <input value={cycleForm.name} required
                placeholder="Q3 2026 Review"
                onChange={e => setCycleForm({ ...cycleForm, name: e.target.value })} />
            </div>
          </div>
          <div className="form-row">
            <div>
              <label>Start Date</label>
              <input type="date" value={cycleForm.start_date} required
                onChange={e => setCycleForm({ ...cycleForm, start_date: e.target.value })} />
            </div>
            <div>
              <label>End Date</label>
              <input type="date" value={cycleForm.end_date} required
                onChange={e => setCycleForm({ ...cycleForm, end_date: e.target.value })} />
            </div>
          </div>
          <button type="submit" disabled={savingCycle}>{savingCycle ? "Saving…" : "Create Cycle"}</button>
        </form>
      )}

      {cycles.length === 0 ? (
        <div className="empty-state muted">No performance cycles yet. Create one above.</div>
      ) : (
        <div className="job-list">
          {cycles.map((cycle) => (
            <div key={cycle.cycle_id}>
              <div className="card" style={{ marginBottom: "4px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ cursor: "pointer", flex: 1 }} onClick={() => handleSelectCycle(cycle.cycle_id)}>
                    <strong>{cycle.name}</strong>
                    <div style={{ display: "flex", gap: "8px", marginTop: "6px", flexWrap: "wrap" }}>
                      <span className={`tag ${cycle.status === "active" ? "tag-green" : cycle.status === "completed" ? "" : ""}`}
                        style={cycle.status === "completed" ? { background: "#ddf4ff", color: "#0550ae" } : {}}>
                        {cycle.status}
                      </span>
                      <span className="muted" style={{ fontSize: "12px" }}>
                        {cycle.start_date} → {cycle.end_date}
                      </span>
                      <span className="muted" style={{ fontSize: "12px" }}>
                        {cycle.participant_ids?.length || 0} participants
                      </span>
                    </div>
                  </div>
                  <div style={{ flexShrink: 0, marginLeft: "12px" }}>
                    {cycle.status === "draft" && (
                      <button className="btn-secondary" style={{ padding: "4px 10px", fontSize: "12px" }}
                        disabled={activating === cycle.cycle_id}
                        onClick={() => handleActivate(cycle.cycle_id)}>
                        {activating === cycle.cycle_id ? "…" : "Activate"}
                      </button>
                    )}
                    <span className="muted" style={{ fontSize: "11px", marginLeft: "8px" }}>
                      {selectedCycle === cycle.cycle_id ? "▲ hide" : "▼ results"}
                    </span>
                  </div>
                </div>
              </div>

              {selectedCycle === cycle.cycle_id && (
                <div className="card" style={{ marginBottom: "8px", background: "#f6f8fa" }}>
                  {resultsLoading ? (
                    <div className="muted">Loading results…</div>
                  ) : !results ? (
                    <div className="muted">No results yet.</div>
                  ) : (
                    <>
                      {/* Score distribution summary */}
                      {results.reviews?.length > 0 && (
                        <div style={{ marginBottom: "1rem" }}>
                          <h4 style={{ marginBottom: "0.5rem" }}>Score Distribution</h4>
                          <table style={{ width: "100%", borderCollapse: "collapse" }}>
                            <thead>
                              <tr>
                                <th style={{ padding: "6px 10px", textAlign: "left" }}>Reviewer</th>
                                <th style={{ padding: "6px 10px", textAlign: "left" }}>Reviewee</th>
                                <th style={{ padding: "6px 10px", textAlign: "right" }}>Score</th>
                                <th style={{ padding: "6px 10px" }}>Submitted</th>
                              </tr>
                            </thead>
                            <tbody>
                              {results.reviews.map((r) => (
                                <tr key={r.review_id} style={{ borderTop: "1px solid #eaeef2" }}>
                                  <td style={{ padding: "6px 10px" }} className="muted">{r.reviewer_id}</td>
                                  <td style={{ padding: "6px 10px" }}>{r.reviewee_id}</td>
                                  <td style={{ padding: "6px 10px", textAlign: "right" }}>
                                    <span style={{ fontWeight: 600, color: scoreColor(r.normalized_score) }}>
                                      {(r.normalized_score * 100).toFixed(0)}%
                                    </span>
                                  </td>
                                  <td style={{ padding: "6px 10px" }} className="muted">
                                    {r.submitted_at ? new Date(r.submitted_at).toLocaleDateString() : "—"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}

                      {/* Promotion readiness predictions */}
                      {results.promotion_predictions?.length > 0 && (
                        <div>
                          <h4 style={{ marginBottom: "0.5rem" }}>Promotion Readiness</h4>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                            {results.promotion_predictions.map((pred, i) => (
                              <div key={i} className="card" style={{
                                padding: "10px 14px", minWidth: "160px", flex: "1",
                                borderLeft: `4px solid ${scoreColor(pred.score)}`,
                              }}>
                                <div className="muted" style={{ fontSize: "11px" }}>
                                  {pred.engineer_id || `Engineer ${i + 1}`}
                                </div>
                                <div style={{ fontSize: "22px", fontWeight: 700, color: scoreColor(pred.score) }}>
                                  {(pred.score * 100).toFixed(0)}%
                                </div>
                                <div className="muted" style={{ fontSize: "11px" }}>
                                  CI: [{pred.confidence_interval?.[0]?.toFixed(2)}, {pred.confidence_interval?.[1]?.toFixed(2)}]
                                </div>
                                <div className="muted" style={{ fontSize: "11px" }}>v{pred.model_version}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {!results.reviews?.length && !results.promotion_predictions?.length && (
                        <div className="muted">No reviews or predictions yet for this cycle.</div>
                      )}
                    </>
                  )}
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

const TABS = ["Jobs", "Onboarding", "Payroll", "Performance", "Compliance", "Integrations", "Analytics"];

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
      {activeTab === "Performance" && <PerformanceTab token={token} />}
      {activeTab === "Compliance" && <ComplianceTab token={token} />}
      {activeTab === "Integrations" && <IntegrationsTab token={token} />}
      {activeTab === "Analytics" && <AnalyticsTab token={token} />}
    </div>
  );
}
