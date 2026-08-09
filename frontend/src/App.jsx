import React, { useEffect, useState } from "react";
import { getHealth } from "./api.js";
import { useAuth } from "./useAuth.js";
import LandingPage from "./LandingPage.jsx";
import JobBoard from "./JobBoard.jsx";
import ApplyPage from "./ApplyPage.jsx";
import EmployerAuth from "./EmployerAuth.jsx";
import EmployerDashboard from "./EmployerDashboard.jsx";
import PricingPage from "./PricingPage.jsx";
import PrivacyPortal from "./PrivacyPortal.jsx";
import { supabase } from "./supabase.js";

const BASE = import.meta.env.VITE_API_BASE || "";

export default function App() {
  const { token, user, login, logout, isLoggedIn } = useAuth();
  const [health, setHealth] = useState(null);
  const [view, setView] = useState("landing"); // landing | jobs | apply | pricing | employer-auth | employer-dash | privacy
  const [applyJobId, setApplyJobId] = useState(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    if (isLoggedIn) setView("employer-dash");
  }, [isLoggedIn]);

  // Handle Supabase OAuth redirect — picks up the session when Google
  // redirects back to the app root (before EmployerAuth is even mounted)
  useEffect(() => {
    if (!supabase || isLoggedIn) return;
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      if ((event === "SIGNED_IN" || event === "INITIAL_SESSION") && session?.user) {
        try {
          const res = await fetch(`${BASE}/api/employer/auth/supabase`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${session.access_token}`,
            },
          });
          if (res.ok) {
            const data = await res.json();
            login(data.token, {
              employer_id: data.employer_id,
              email: data.email,
              company_name: data.company_name,
            });
          }
        } catch (_) {}
      }
    });
    return () => subscription.unsubscribe();
  }, [isLoggedIn]);

  function handleCandidateClick() {
    setView("jobs");
  }

  function handleRecruiterClick() {
    setView("employer-auth");
  }

  function handlePricingClick() {
    setView("pricing");
  }

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

  // Landing page renders standalone — no app shell
  if (view === "landing") {
    return (
      <LandingPage
        onHirerClick={() => setView("employer-auth")}
        onCandidateClick={() => setView("jobs")}
      />
    );
  }

  return (
    <div className="app">
      <header>
        <div className="header-brand" onClick={() => setView("landing")} style={{ cursor: "pointer" }}>
          <h1>HireAI</h1>
          {health && (
            <span className="tag">{health.mock ? "MOCK mode" : `AI: ${health.model}`}</span>
          )}
        </div>
        <nav className="header-nav">
          {view !== "employer-auth" && view !== "employer-dash" && (
            <>
              <button className="btn-ghost" onClick={() => setView("landing")}>Home</button>
              <button className={view === "jobs" ? "nav-active" : "btn-ghost"}
                onClick={() => setView("jobs")}>Jobs</button>
              <button className={view === "pricing" ? "nav-active" : "btn-ghost"}
                onClick={() => setView("pricing")}>Pricing</button>
              <button className="btn-ghost" onClick={() => setView("privacy")}>Privacy</button>
              <button className="btn-secondary" onClick={() => setView("employer-auth")}>For employers</button>
            </>
          )}
          {view === "employer-dash" && (
            <>
              <button className="btn-ghost" onClick={() => setView("pricing")}>Pricing</button>
              <button className="btn-ghost" onClick={handleLogout}>Logout</button>
            </>
          )}
          {view === "employer-auth" && (
            <button className="btn-ghost" onClick={() => setView("landing")}>← Back home</button>
          )}
          {(view === "pricing" && !isLoggedIn) && (
            <button className="btn-ghost" onClick={() => setView("landing")}>← Back</button>
          )}
          {(view === "pricing" && isLoggedIn) && (
            <button className="btn-ghost" onClick={() => setView("employer-dash")}>← Dashboard</button>
          )}
        </nav>
      </header>

      <main>
        {view === "jobs" && <JobBoard onApply={handleApply} />}
        {view === "apply" && applyJobId && (
          <ApplyPage jobId={applyJobId} onBack={() => setView("jobs")} />
        )}
        {view === "pricing" && (
          <PricingPage
            token={token}
            user={user}
            onLoginRequired={() => setView("employer-auth")}
            onUpgraded={() => setView("employer-dash")}
          />
        )}
        {view === "employer-auth" && (
          <EmployerAuth onAuth={handleEmployerAuth} />
        )}
        {view === "employer-dash" && isLoggedIn && (
          <EmployerDashboard
            user={user}
            token={token}
            onLogout={handleLogout}
            onUpgrade={() => setView("pricing")}
          />
        )}
        {view === "privacy" && (
          <PrivacyPortal onBack={() => setView("landing")} />
        )}
      </main>
    </div>
  );
}
