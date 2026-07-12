import { useEffect, useRef } from "react";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

/**
 * Loads Google Identity Services and renders the sign-in button.
 * onSuccess(profile) => { name, email, credential }
 */
export function useGoogleAuth(buttonId, onSuccess) {
  const initialised = useRef(false);

  function init() {
    if (!window.google || !GOOGLE_CLIENT_ID || initialised.current) return;
    initialised.current = true;
    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: (resp) => {
        // Decode JWT payload to get name/email without a server round-trip
        const payload = JSON.parse(atob(resp.credential.split(".")[1]));
        onSuccess({ name: payload.name || "", email: payload.email || "", credential: resp.credential });
      },
    });
    const el = document.getElementById(buttonId);
    if (el) {
      window.google.accounts.id.renderButton(el, {
        theme: "outline", size: "large", width: "100%", text: "continue_with",
      });
    }
  }

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    if (window.google) { init(); return; }
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = init;
    document.head.appendChild(script);
    return () => {
      // only remove if we added it
      if (document.head.contains(script)) document.head.removeChild(script);
    };
  }, [buttonId]);
}

export { GOOGLE_CLIENT_ID };
