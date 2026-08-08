import React, { useState, useEffect } from "react";
import { employerRegister, employerLogin } from "./api.js";
import { supabase } from "./supabase.js";

const BASE = import.meta.env.VITE_API_BASE || "";

export default function EmployerAuth({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", company_name: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Handle Supabase OAuth callback — fires when user returns from Google
  useEffect(() => {
    if (!supabase) return;
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      if ((event === "SIGNED_IN" || event === "INITIAL_SESSION") && session?.user) {
        await handleSupabaseSession(session);
      }
    });
    return () => subscription.unsubscribe();
  }, []);

  async function handleSupabaseSession(session) {
    setLoading(true);
    setError("");
    try {
      // Send the Supabase access token to the backend — it verifies via Supabase JWT secret
      const res = await fetch(`${BASE}/api/employer/auth/supabase`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${session.access_token}`,
        },
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail || res.statusText);
      }
      const data = await res.json();
      onAuth(data.token, {
        employer_id: data.employer_id,
        email: data.email,
        company_name: data.company_name,
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleLogin() {
    if (!supabase) {
      setError("Supabase not configured — set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY");
      return;
    }
    setError("");
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin },
    });
    if (oauthError) setError(oauthError.message);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = mode === "login"
        ? await employerLogin({ email: form.email, password: form.password })
        : await employerRegister({ email: form.email, password: form.password, company_name: form.company_name });
      onAuth(data.token, {
        employer_id: data.employer_id,
        email: data.email,
        company_name: data.company_name,
      });
    } catch (e) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card card">
        <h2>{mode === "login" ? "Employer login" : "Create employer account"}</h2>

        {/* Google OAuth via Supabase */}
        <button
          type="button"
          className="google-btn"
          onClick={handleGoogleLogin}
          disabled={loading}
          style={{
            display: "flex", alignItems: "center", gap: "10px", width: "100%",
            padding: "10px 16px", border: "1px solid #d0d7de", borderRadius: "8px",
            background: "#fff", color: "#1f2328", fontSize: "14px", fontWeight: 500,
            cursor: "pointer", marginBottom: "12px", justifyContent: "center",
          }}
        >
          <svg width="18" height="18" viewBox="0 0 48 48">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
          </svg>
          Continue with Google
        </button>

        <div className="auth-divider"><span>or</span></div>

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
