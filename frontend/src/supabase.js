import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY;

// null when env vars aren't set — callers must guard with `if (!supabase)`
export const supabase = url && key ? createClient(url, key) : null;

const redirect = () => window.location.origin;

/** Google OAuth — redirects to Google consent screen */
export async function signInWithGoogle() {
  if (!supabase) throw new Error("Supabase not configured");
  return supabase.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: redirect() },
  });
}

/** LinkedIn OIDC — must use 'linkedin_oidc', not 'linkedin' */
export async function signInWithLinkedIn() {
  if (!supabase) throw new Error("Supabase not configured");
  return supabase.auth.signInWithOAuth({
    provider: "linkedin_oidc",
    options: {
      redirectTo: redirect(),
      scopes: "openid profile email",
    },
  });
}

/** Magic link — sends OTP email, no password required */
export async function signInWithEmailMagicLink(email) {
  if (!supabase) throw new Error("Supabase not configured");
  return supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: redirect() },
  });
}

/** Standard email + password login */
export async function signInWithEmailAndPassword(email, password) {
  if (!supabase) throw new Error("Supabase not configured");
  return supabase.auth.signInWithPassword({ email, password });
}

/** Sign out current session */
export async function signOut() {
  if (!supabase) return;
  return supabase.auth.signOut();
}
