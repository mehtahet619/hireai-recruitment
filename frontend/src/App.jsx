import React, { useEffect, useState } from "react";
import { getHealth } from "./api.js";
import { useAuth } from "./useAuth.js";
import JobBoard from "./JobBoard.jsx";
import ApplyPage from "./ApplyPage.jsx";
import EmployerAuth from "./EmployerAuth.jsx";
import EmployerDashboard from "./EmployerDashboard.jsx";

export default function App() {
  const { token, user, login, logout, isLoggedIn } = useAuth();
  const [health, setHealth] = useState(null);
  const [view, setView] = useState("jobs"); // jobs | apply | employer-auth | employer-dash
  const [applyJobId, setApplyJobId] = useState(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    if (isLoggedIn) setView("employer-dash");
  }, [isLoggedIn]);

  function handleApply(jobId) {
    setApplyJobId(jobId);
    setView("apply");
  }

  function handleEmployerAuth(tokenValue, userData) {
    login(tokenValue, userData);
    setView("employer-dash");
  }

  function handleLogout() {
    logout();
    setView("jobs");
  }

  return (
    <div className="app">
      <header>
        <div className="header-brand" onClick={() => setView("jobs")} style={{ cursor: "pointer" }}>
          <h1>HireAI</h1>
          {health && (
            <span className="tag">{health.mock ? "MOCK mode" : `AI: ${health.model}`}</span>
          )}
        </div>
        <nav className="header-nav">
          {view !== "employer-auth" && view !== "employer-dash" && (
            <>
              <button className={view === "jobs" ? "nav-active" : "btn-ghost"}
                onClick={() => setView("jobs")}>Jobs</button>
              <button className="btn-secondary"
                onClick={() => setView("employer-auth")}>For employers</button>
            </>
          )}
          {view === "employer-dash" && (
            <button className="btn-ghost" onClick={handleLogout}>Logout</button>
          )}
          {view === "employer-auth" && (
            <button className="btn-ghost" onClick={() => setView("jobs")}>← Back to jobs</button>
          )}
        </nav>
      </header>

      <main>
        {view === "jobs" && <JobBoard onApply={handleApply} />}
        {view === "apply" && applyJobId && (
          <ApplyPage jobId={applyJobId} onBack={() => setView("jobs")} />
        )}
        {view === "employer-auth" && (
          <EmployerAuth onAuth={handleEmployerAuth} />
        )}
        {view === "employer-dash" && isLoggedIn && (
          <EmployerDashboard user={user} token={token} onLogout={handleLogout} />
        )}
      </main>
    </div>
  );
}
