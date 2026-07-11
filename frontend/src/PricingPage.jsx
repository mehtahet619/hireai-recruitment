import React, { useEffect, useState } from "react";

const RAZORPAY_KEY_ID = import.meta.env.VITE_RAZORPAY_KEY_ID || "";
const BASE = import.meta.env.VITE_API_BASE || "";

function loadRazorpay() {
  return new Promise((resolve) => {
    if (window.Razorpay) return resolve(true);
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
}

export default function PricingPage({ token, user, onUpgraded, onLoginRequired }) {
  const [plans, setPlans] = useState([]);
  const [currentPlan, setCurrentPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [paying, setPaying] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    fetch(`${BASE}/api/pricing`)
      .then((r) => r.json())
      .then((d) => setPlans(d.plans || []));

    if (token) {
      fetch(`${BASE}/api/employer/plan`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => r.json())
        .then(setCurrentPlan)
        .catch(() => {});
    }
  }, [token]);

  async function handleSubscribe(plan) {
    if (!token) return onLoginRequired();
    if (plan.id === "enterprise") {
      window.open("mailto:sales@hireai.com?subject=Enterprise Plan Enquiry", "_blank");
      return;
    }

    setError("");
    setSuccess("");
    setPaying(plan.id);
    setLoading(true);

    const loaded = await loadRazorpay();
    if (!loaded) {
      setError("Failed to load payment gateway. Please try again.");
      setLoading(false);
      setPaying(null);
      return;
    }

    try {
      const res = await fetch(`${BASE}/api/employer/payment/create-order`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ plan: plan.id }),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || "Failed to create order");
      }
      const order = await res.json();

      const options = {
        key: order.key_id || RAZORPAY_KEY_ID,
        amount: order.amount,
        currency: order.currency,
        name: "HireAI",
        description: `${plan.name} Plan — ₹${plan.price}/month`,
        order_id: order.order_id,
        prefill: { email: user?.email || "" },
        theme: { color: "#1f6feb" },
        handler: async (response) => {
          try {
            const vres = await fetch(`${BASE}/api/employer/payment/verify`, {
              method: "POST",
              headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
              body: JSON.stringify({
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
                plan: plan.id,
              }),
            });
            if (!vres.ok) throw new Error("Payment verification failed");
            const vdata = await vres.json();
            setSuccess(vdata.message);
            setCurrentPlan({ plan: vdata.plan, plan_expires_at: vdata.plan_expires_at });
            onUpgraded && onUpgraded(vdata.plan);
          } catch (e) {
            setError(e.message);
          } finally {
            setLoading(false);
            setPaying(null);
          }
        },
        modal: {
          ondismiss: () => {
            setLoading(false);
            setPaying(null);
          },
        },
      };

      const rzp = new window.Razorpay(options);
      rzp.open();
    } catch (e) {
      setError(e.message);
      setLoading(false);
      setPaying(null);
    }
  }

  const activePlan = currentPlan?.plan || "free";

  return (
    <div className="pricing-page">
      <div className="pricing-header">
        <h2>Simple, transparent pricing</h2>
        <p className="muted">Candidates apply for free. Companies pay to post jobs.</p>
      </div>

      {error && <p className="error" style={{ textAlign: "center" }}>{error}</p>}
      {success && <p className="notice success" style={{ textAlign: "center", marginBottom: "16px" }}>{success}</p>}

      {currentPlan && activePlan !== "free" && (
        <div className="current-plan-banner">
          Active plan: <strong>{activePlan.charAt(0).toUpperCase() + activePlan.slice(1)}</strong>
          {currentPlan.plan_expires_at && (
            <span className="muted"> · renews {new Date(currentPlan.plan_expires_at).toLocaleDateString("en-IN")}</span>
          )}
        </div>
      )}

      <div className="pricing-grid">
        {/* Free for candidates */}
        <div className="pricing-card">
          <div className="pricing-card-header">
            <h3>Candidate</h3>
            <div className="price">
              <span className="price-amount">Free</span>
            </div>
          </div>
          <ul className="feature-list">
            <li>✓ Browse all job openings</li>
            <li>✓ Apply with resume</li>
            <li>✓ AI-powered interview</li>
            <li>✓ Instant scoring &amp; feedback</li>
            <li>✓ No account needed</li>
          </ul>
          <div className="pricing-cta">
            <span className="tag tag-green">Always free</span>
          </div>
        </div>

        {plans.map((plan) => {
          const isActive = activePlan === plan.id;
          const isBusy = paying === plan.id && loading;
          return (
            <div key={plan.id} className={`pricing-card ${plan.id === "growth" ? "featured" : ""} ${isActive ? "active-plan" : ""}`}>
              {plan.id === "growth" && <div className="popular-badge">Most popular</div>}
              {isActive && <div className="active-badge">Current plan</div>}
              <div className="pricing-card-header">
                <h3>{plan.name}</h3>
                <div className="price">
                  {plan.price ? (
                    <>
                      <span className="price-currency">₹</span>
                      <span className="price-amount">{plan.price}</span>
                      <span className="price-period">/month</span>
                    </>
                  ) : (
                    <span className="price-amount">Custom</span>
                  )}
                </div>
              </div>
              <ul className="feature-list">
                {plan.features.map((f, i) => <li key={i}>✓ {f}</li>)}
              </ul>
              <div className="pricing-cta">
                {plan.id === "enterprise" ? (
                  <button className="btn-secondary" onClick={() => handleSubscribe(plan)}>
                    Contact sales
                  </button>
                ) : isActive ? (
                  <button disabled className="btn-secondary">Active</button>
                ) : (
                  <button onClick={() => handleSubscribe(plan)} disabled={isBusy}>
                    {isBusy ? "Processing…" : `Subscribe — ₹${plan.price}/mo`}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <p className="pricing-note muted">
        All plans renew monthly. Cancel anytime. Prices in Indian Rupees (INR).
        Enterprise pricing is custom — contact us for a quote.
      </p>
    </div>
  );
}
