import { useCallback, useState } from "react";

const BASE = import.meta.env.VITE_API_BASE || "";
const MAX_LATENCY_MS = 2500;
const PING_COUNT = 3;

export function useNetworkCheck() {
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [metrics, setMetrics] = useState(null);

  const check = useCallback(async () => {
    setStatus("checking");
    setError("");

    try {
      const samples = [];
      for (let i = 0; i < PING_COUNT; i++) {
        const start = performance.now();
        const res = await fetch(`${BASE}/api/health`, { cache: "no-store" });
        if (!res.ok) throw new Error("Cannot reach interview server.");
        await res.json();
        samples.push(performance.now() - start);
      }

      const latencyMs = Math.round(samples.reduce((a, b) => a + b, 0) / samples.length);
      const ok = latencyMs <= MAX_LATENCY_MS;
      const result = { latencyMs, ok };
      setMetrics(result);

      if (!ok) {
        setStatus("error");
        setError(
          `Network too slow (${latencyMs}ms avg). Need under ${MAX_LATENCY_MS}ms to continue.`
        );
        return false;
      }

      setStatus("ready");
      return true;
    } catch (e) {
      setStatus("error");
      setError(e.message || "Network check failed.");
      return false;
    }
  }, []);

  return { status, error, metrics, check };
}
