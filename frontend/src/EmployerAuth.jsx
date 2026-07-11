import React, { useState, useEffect } from "react";
import { employerRegister, employerLogin } from "./api.js";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

export default function EmployerAuth({ onAuth }) {
  const [mode, setMode] = useState("login"); // login | register
  const [form, setForm] = useState({ email: "", password: "", company_name: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Load Google Identity Services script
  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = initGoogle;
    document.head.appendChild(script);
    return () => document.head.removeChild(script);
  }, []);

  function initGoogle() {
    if (!window.google || !GOOGLE_CLIENT_ID) return;
    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: handleGoogleCredential,
    });
    window.google.accounts.id.renderButton(
      document.getElementById("google-btn"),
      { theme: "outline", size: "large", width: "100%", text: "continue_with" }
    );
  }

  async function handleGoogleCredential(response) {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE || ""}/api/employer/auth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential: response.credential }),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || res.statusText);
      }
      const data = await res.json();
      onAuth(data.token, { employer_id: data.employer_id, email: data.email, company_name: data.company_name });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = mode === "login"
        ? await employerLogin({ email: form.email, password: form.password })
        : await employerRegister({ email: form.email, password: form.password, company_name: form.company_name });
      onAuth(data.token, { employer_id: data.employer_id, email: data.email, company_name: data.company_name });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card card">
        <h2>{mode === "login" ? "Employer login" : "Create employer account"}</h2>

        {/* Google Sign-In */}
        {GOOGLE_CLIENT_ID && (
          <>
            <div id="google-btn" style={{ marginBottom: "12px" }} />
            <div className="auth-divider"><span>or</span></div>
          </>
        )}

        {error && <p className="error">{error}</p>}
        <form onSubmit={handleSubmit}>
          {mode === "register" && (
            <>
              <label>Company name</label>
              <input value={form.company_name}
                onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                placeholder="Acme Corp" required />
            </>
          )}
          <label>Email</label>
          <input type="email" value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="hr@company.com" required />
          <label>Password</label>
          <input type="password" value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            placeholder="••••••••" required minLength={6} />
          <button type="submit" disabled={loading}>
            {loading ? "Please wait…" : mode === "login" ? "Login" : "Create account"}
          </button>
        </form>
        <p className="auth-switch">
          {mode === "login" ? "Don't have an account? " : "Already have an account? "}
          <button className="btn-link" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
            {mode === "login" ? "Register" : "Login"}
          </button>
        </p>
      </div>
    </div>
  );
}
