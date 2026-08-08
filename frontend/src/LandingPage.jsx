import React, { useEffect, useRef, useState } from "react";
import "./landing.css";
import { motion, useScroll, useTransform, useInView, AnimatePresence, useMotionValue, useSpring } from "framer-motion";
import {
  Zap, Brain, Shield, BarChart3, Users, Clock, Check, Star, ChevronDown,
  ArrowRight, Play, GitBranch, Mail, Globe2, Menu, X, Sparkles, TrendingUp, Globe
} from "lucide-react";

// ── Animation variants ────────────────────────────────────────────────────────
const fadeUp = { hidden: { opacity: 0, y: 40 }, visible: { opacity: 1, y: 0, transition: { duration: 0.7, ease: "easeOut" } } };
const fadeIn = { hidden: { opacity: 0 }, visible: { opacity: 1, transition: { duration: 0.6 } } };
const stagger = { visible: { transition: { staggerChildren: 0.12 } } };
const slideLeft = { hidden: { opacity: 0, x: -60 }, visible: { opacity: 1, x: 0, transition: { duration: 0.7, ease: "easeOut" } } };
const slideRight = { hidden: { opacity: 0, x: 60 }, visible: { opacity: 1, x: 0, transition: { duration: 0.7, ease: "easeOut" } } };
const scaleIn = { hidden: { opacity: 0, scale: 0.85 }, visible: { opacity: 1, scale: 1, transition: { duration: 0.5, ease: "easeOut" } } };

// ── Reusable: Section heading ─────────────────────────────────────────────────
function SectionHeading({ badge, title, subtitle }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  return (
    <motion.div ref={ref} variants={stagger} initial="hidden" animate={inView ? "visible" : "hidden"} className="lp-section-heading">
      {badge && <motion.span variants={fadeUp} className="lp-badge">{badge}</motion.span>}
      <motion.h2 variants={fadeUp} className="lp-h2">{title}</motion.h2>
      {subtitle && <motion.p variants={fadeUp} className="lp-subtitle">{subtitle}</motion.p>}
    </motion.div>
  );
}

// ── Navbar ────────────────────────────────────────────────────────────────────
function Navbar({ onHirerClick, onCandidateClick }) {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", fn);
    return () => window.removeEventListener("scroll", fn);
  }, []);
  return (
    <motion.nav initial={{ y: -80, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.6, ease: "easeOut" }}
      className={`lp-nav ${scrolled ? "lp-nav-scrolled" : ""}`}>
      <div className="lp-nav-inner">
        <div className="lp-nav-brand">
          <div className="lp-logo-dot" /><span className="lp-logo-text">HireAI</span>
        </div>
        <div className="lp-nav-links">
          {["Features", "How it works", "Pricing", "FAQ"].map(l => (
            <a key={l} href={`#${l.toLowerCase().replace(/ /g, "-")}`} className="lp-nav-link">{l}</a>
          ))}
        </div>
        <div className="lp-nav-actions">
          <motion.button whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }} className="lp-btn-ghost" onClick={onCandidateClick}>Find jobs</motion.button>
          <motion.button whileHover={{ scale: 1.06 }} whileTap={{ scale: 0.95 }} className="lp-btn-primary" onClick={onHirerClick}>Post a job</motion.button>
        </div>
        <button className="lp-menu-toggle" onClick={() => setMenuOpen(!menuOpen)}>
          {menuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>
      <AnimatePresence>
        {menuOpen && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3 }} className="lp-mobile-menu">
            {["Features", "How it works", "Pricing", "FAQ"].map(l => (
              <a key={l} href={`#${l.toLowerCase().replace(/ /g, "-")}`} className="lp-mobile-link" onClick={() => setMenuOpen(false)}>{l}</a>
            ))}
            <button className="lp-btn-outline" style={{ margin: "4px 0" }} onClick={() => { setMenuOpen(false); onCandidateClick(); }}>Find jobs</button>
            <button className="lp-btn-primary" style={{ width: "100%", marginTop: "4px" }} onClick={() => { setMenuOpen(false); onHirerClick(); }}>Post a job</button>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  );
}

// ── Floating blobs ────────────────────────────────────────────────────────────
function Blobs() {
  return (
    <div className="lp-blobs" aria-hidden>
      <motion.div className="lp-blob lp-blob-1" animate={{ x: [0,40,-20,0], y: [0,-30,20,0] }} transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }} />
      <motion.div className="lp-blob lp-blob-2" animate={{ x: [0,-30,20,0], y: [0,40,-20,0] }} transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }} />
      <motion.div className="lp-blob lp-blob-3" animate={{ x: [0,20,-40,0], y: [0,-20,30,0] }} transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }} />
    </div>
  );
}

// ── Particles ─────────────────────────────────────────────────────────────────
function Particles() {
  const pts = Array.from({ length: 30 }, (_, i) => ({
    id: i, x: Math.random() * 100, y: Math.random() * 100,
    size: Math.random() * 2 + 1, dur: Math.random() * 10 + 8,
  }));
  return (
    <div className="lp-particles" aria-hidden>
      {pts.map(p => (
        <motion.div key={p.id} className="lp-particle"
          style={{ left: `${p.x}%`, top: `${p.y}%`, width: p.size, height: p.size }}
          animate={{ y: [0, -30, 0], opacity: [0.2, 0.7, 0.2] }}
          transition={{ duration: p.dur, repeat: Infinity, ease: "easeInOut", delay: p.id * 0.3 }} />
      ))}
    </div>
  );
}

// ── Hero ──────────────────────────────────────────────────────────────────────
function Hero({ onHirerClick, onCandidateClick }) {
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const springX = useSpring(mouseX, { stiffness: 60, damping: 20 });
  const springY = useSpring(mouseY, { stiffness: 60, damping: 20 });
  const handleMouse = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    mouseX.set((e.clientX - r.left - r.width / 2) / 30);
    mouseY.set((e.clientY - r.top - r.height / 2) / 30);
  };
  return (
    <section className="lp-hero" onMouseMove={handleMouse}>
      <Blobs />
      <Particles />
      <div className="lp-hero-grid" />
      <motion.div className="lp-hero-content" variants={stagger} initial="hidden" animate="visible">
        <motion.div variants={fadeUp} className="lp-hero-badge">
          <Sparkles size={14} /><span>AI-Powered Recruiting, Reimagined</span>
        </motion.div>
        <motion.h1 variants={fadeUp} className="lp-h1">
          Hire the best engineers{" "}
          <span className="lp-gradient-text">10× faster</span>{" "}
          with AI interviews
        </motion.h1>
        <motion.p variants={fadeUp} className="lp-hero-sub">
          HireAI automates technical screening with intelligent AI interviews, instant scoring,
          and bias-free candidate evaluation — so your team focuses on what matters.
        </motion.p>
        <motion.div variants={fadeUp} className="lp-portal-choice">
          <motion.button whileHover={{ scale: 1.06, boxShadow: "0 0 40px rgba(99,102,241,0.5)" }}
            whileTap={{ scale: 0.95 }} className="lp-portal-btn lp-portal-hirer" onClick={onHirerClick}>
            <div className="lp-portal-icon">🏢</div>
            <div>
              <div className="lp-portal-label">I'm hiring</div>
              <div className="lp-portal-desc">Post jobs & review AI-screened candidates</div>
            </div>
            <ArrowRight size={18} className="lp-portal-arrow" />
          </motion.button>
          <motion.button whileHover={{ scale: 1.06, boxShadow: "0 0 40px rgba(56,189,248,0.3)" }}
            whileTap={{ scale: 0.95 }} className="lp-portal-btn lp-portal-candidate" onClick={onCandidateClick}>
            <div className="lp-portal-icon">🧑‍💻</div>
            <div>
              <div className="lp-portal-label">I'm job hunting</div>
              <div className="lp-portal-desc">Browse openings & get AI-interviewed instantly</div>
            </div>
            <ArrowRight size={18} className="lp-portal-arrow" />
          </motion.button>
        </motion.div>
        <motion.p variants={fadeUp} className="lp-hero-note">Free for candidates · No credit card required for employers</motion.p>
      </motion.div>
      <motion.div className="lp-hero-visual" style={{ x: springX, y: springY }}>
        <DashboardMockup />
      </motion.div>
      <motion.div className="lp-scroll-indicator" animate={{ y: [0, 10, 0] }} transition={{ duration: 2, repeat: Infinity }}>
        <ChevronDown size={22} />
      </motion.div>
    </section>
  );
}

// ── Dashboard mockup ──────────────────────────────────────────────────────────
function DashboardMockup() {
  const candidates = [
    { name: "Alex Chen", score: 94, band: "Strong Advance", color: "#22c55e" },
    { name: "Maya Patel", score: 87, band: "Advance", color: "#3b82f6" },
    { name: "Jordan Lee", score: 72, band: "Borderline", color: "#f59e0b" },
  ];
  return (
    <motion.div className="lp-mockup" initial={{ opacity: 0, y: 60, scale: 0.92 }} animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.9, delay: 0.4, ease: "easeOut" }}>
      <div className="lp-mockup-bar">
        <span className="lp-dot red" /><span className="lp-dot yellow" /><span className="lp-dot green" />
        <span className="lp-mockup-title">HireAI Dashboard</span>
      </div>
      <div className="lp-mockup-body">
        <div className="lp-mockup-row">
          {[{ label: "Candidates", val: "248", icon: <Users size={14}/> }, { label: "Avg Score", val: "87%", icon: <TrendingUp size={14}/> }, { label: "Time saved", val: "94h", icon: <Clock size={14}/> }].map(s => (
            <div key={s.label} className="lp-mockup-stat">
              <span className="lp-mockup-stat-icon">{s.icon}</span>
              <span className="lp-mockup-stat-val">{s.val}</span>
              <span className="lp-mockup-stat-label">{s.label}</span>
            </div>
          ))}
        </div>
        <div className="lp-mockup-section-label">Recent interviews</div>
        {candidates.map((c, i) => (
          <motion.div key={c.name} className="lp-mockup-candidate"
            initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.7 + i * 0.15 }}>
            <div className="lp-mockup-avatar">{c.name[0]}</div>
            <div className="lp-mockup-cand-info">
              <span className="lp-mockup-cand-name">{c.name}</span>
              <span className="lp-mockup-cand-band" style={{ color: c.color }}>{c.band}</span>
            </div>
            <div className="lp-mockup-score" style={{ color: c.color }}>{c.score}</div>
          </motion.div>
        ))}
        <div className="lp-mockup-chart">
          {[60,75,85,70,94,88,92].map((h, i) => (
            <motion.div key={i} className="lp-chart-bar"
              initial={{ scaleY: 0 }} animate={{ scaleY: 1 }}
              transition={{ delay: 1 + i * 0.07, duration: 0.4, ease: "easeOut" }}
              style={{ height: `${h}%` }} />
          ))}
        </div>
      </div>
    </motion.div>
  );
}

// ── Logo cloud ────────────────────────────────────────────────────────────────
const LOGOS = ["Google", "Microsoft", "Stripe", "Airbnb", "Notion", "Linear", "Vercel", "Figma", "Slack", "GitHub"];
function LogoCloud() {
  return (
    <section className="lp-logos-section">
      <p className="lp-logos-label">Trusted by teams at</p>
      <div className="lp-logos-track-wrap">
        <motion.div className="lp-logos-track" animate={{ x: ["0%", "-50%"] }}
          transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
          whileHover={{ animationPlayState: "paused" }}>
          {[...LOGOS, ...LOGOS].map((l, i) => (
            <span key={i} className="lp-logo-item">{l}</span>
          ))}
        </motion.div>
        <div className="lp-logos-fade-l" /><div className="lp-logos-fade-r" />
      </div>
    </section>
  );
}

// ── Features ──────────────────────────────────────────────────────────────────
const FEATURES = [
  { icon: <Brain size={24}/>, title: "AI Technical Interviews", desc: "Aria conducts intelligent, adaptive interviews that probe depth — not just keywords." },
  { icon: <BarChart3 size={24}/>, title: "Instant Scoring", desc: "Every candidate gets an objective score with detailed breakdown the moment they finish." },
  { icon: <Shield size={24}/>, title: "Bias-Free Evaluation", desc: "Structured, consistent interviews eliminate unconscious bias from your hiring funnel." },
  { icon: <Zap size={24}/>, title: "10× Faster Screening", desc: "Screen 100 candidates in the time it takes to review 10 resumes manually." },
  { icon: <Globe size={24}/>, title: "Any Stack, Any Role", desc: "Works for frontend, backend, data, ML, DevOps — configure once, run everywhere." },
  { icon: <Users size={24}/>, title: "Team Collaboration", desc: "Share reviews, leave notes, and make decisions together inside one dashboard." },
];
function FeatureCard({ f, i }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <motion.div ref={ref} variants={scaleIn} initial="hidden" animate={inView ? "visible" : "hidden"}
      transition={{ delay: (i % 3) * 0.1 }}
      whileHover={{ y: -6, boxShadow: "0 20px 60px rgba(99,102,241,0.15)" }}
      className="lp-feature-card">
      <div className="lp-feature-icon">{f.icon}</div>
      <h3 className="lp-feature-title">{f.title}</h3>
      <p className="lp-feature-desc">{f.desc}</p>
    </motion.div>
  );
}

function Features() {
  return (
    <section id="features" className="lp-section">
      <SectionHeading badge="Features" title="Everything you need to hire smarter" subtitle="One platform to screen, evaluate, and collaborate on every engineering hire." />
      <div className="lp-features-grid">
        {FEATURES.map((f, i) => <FeatureCard key={f.title} f={f} i={i} />)}
      </div>
    </section>
  );
}

// ── How it works ──────────────────────────────────────────────────────────────
const STEPS = [
  { n: "01", title: "Post a job", desc: "Describe your role. HireAI parses the JD and configures a custom interview automatically." },
  { n: "02", title: "Candidates apply", desc: "Applicants submit their resume and are immediately placed into an AI-driven technical interview." },
  { n: "03", title: "AI interviews everyone", desc: "Aria adapts questions in real time, probing depth, reasoning, and communication style." },
  { n: "04", title: "Review scored results", desc: "Your dashboard shows ranked candidates with transcripts, scores, and hiring recommendations." },
];
function Step({ s, i }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <motion.div ref={ref} variants={i % 2 === 0 ? slideLeft : slideRight}
      initial="hidden" animate={inView ? "visible" : "hidden"} className="lp-step">
      <div className="lp-step-num">{s.n}</div>
      <div className="lp-step-content">
        <h3 className="lp-step-title">{s.title}</h3>
        <p className="lp-step-desc">{s.desc}</p>
      </div>
    </motion.div>
  );
}

function HowItWorks() {
  return (
    <section id="how-it-works" className="lp-section lp-section-alt">
      <SectionHeading badge="Process" title="From job post to shortlist in hours" />
      <div className="lp-timeline">
        {STEPS.map((s, i) => <Step key={s.n} s={s} i={i} />)}
      </div>
    </section>
  );
}

// ── Stats ─────────────────────────────────────────────────────────────────────
function Counter({ to, suffix = "" }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!inView) return;
    let start = 0;
    const step = to / 60;
    const timer = setInterval(() => {
      start += step;
      if (start >= to) { setVal(to); clearInterval(timer); }
      else setVal(Math.floor(start));
    }, 16);
    return () => clearInterval(timer);
  }, [inView, to]);
  return <span ref={ref}>{val.toLocaleString()}{suffix}</span>;
}

const STATS = [
  { label: "Candidates screened", val: 12000, suffix: "+" },
  { label: "Companies hiring", val: 480, suffix: "+" },
  { label: "Hours saved per hire", val: 24, suffix: "h" },
  { label: "Platform uptime", val: 99, suffix: ".9%" },
];
function Stats() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <section className="lp-stats-section">
      <motion.div ref={ref} className="lp-stats-grid" variants={stagger} initial="hidden" animate={inView ? "visible" : "hidden"}>
        {STATS.map(s => (
          <motion.div key={s.label} variants={scaleIn} className="lp-stat-card">
            <div className="lp-stat-val"><Counter to={s.val} suffix={s.suffix} /></div>
            <div className="lp-stat-label">{s.label}</div>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}

// ── Testimonials ──────────────────────────────────────────────────────────────
const TESTIMONIALS = [
  { name: "Sarah Kim", role: "VP Engineering, Finly", text: "We cut our screening time from 3 weeks to 3 days. HireAI's scoring is eerily accurate — every A-player it flagged has been a top performer.", stars: 5 },
  { name: "Marcus Webb", role: "CTO, BuildStack", text: "The AI interviews are genuinely impressive. Candidates say it feels fair and thorough. Our offer acceptance rate went up because the process became faster.", stars: 5 },
  { name: "Priya Nair", role: "Head of Talent, Zerobase", text: "Finally a tool that gives engineers a real interview experience, not just a quiz. The transcripts help us onboard faster too.", stars: 5 },
];
function Testimonials() {
  const [active, setActive] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setActive(a => (a + 1) % TESTIMONIALS.length), 5000);
    return () => clearInterval(t);
  }, []);
  return (
    <section className="lp-section lp-section-alt">
      <SectionHeading badge="Testimonials" title="Loved by hiring teams" />
      <div className="lp-testimonials">
        <AnimatePresence mode="wait">
          <motion.div key={active} initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -30 }} transition={{ duration: 0.5 }} className="lp-testimonial-card">
            <div className="lp-stars">{Array(TESTIMONIALS[active].stars).fill(0).map((_, i) => <Star key={i} size={16} fill="#fbbf24" color="#fbbf24" />)}</div>
            <p className="lp-testimonial-text">"{TESTIMONIALS[active].text}"</p>
            <div className="lp-testimonial-author">
              <div className="lp-testimonial-avatar">{TESTIMONIALS[active].name[0]}</div>
              <div>
                <div className="lp-testimonial-name">{TESTIMONIALS[active].name}</div>
                <div className="lp-testimonial-role">{TESTIMONIALS[active].role}</div>
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
        <div className="lp-dots">
          {TESTIMONIALS.map((_, i) => (
            <button key={i} className={`lp-dot-btn ${i === active ? "active" : ""}`} onClick={() => setActive(i)} aria-label={`Testimonial ${i+1}`} />
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Pricing ───────────────────────────────────────────────────────────────────
const PRICING = [
  { name: "Free", price: 0, period: "forever", features: ["1 active job post", "AI interviews", "Candidate scoring", "Basic analytics"], cta: "Get started", highlight: false },
  { name: "Growth", price: 199, period: "month", features: ["20 active job posts", "AI interviews", "Advanced scoring", "Full analytics", "Priority support"], cta: "Subscribe", highlight: true },
  { name: "Enterprise", price: null, period: "custom", features: ["Unlimited posts", "Custom AI tuning", "Dedicated support", "SLA guarantee", "Custom integrations"], cta: "Contact sales", highlight: false },
];
function PricingCard({ p, i, onGetStarted }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  return (
    <motion.div ref={ref} variants={fadeUp} initial="hidden" animate={inView ? "visible" : "hidden"}
      transition={{ delay: i * 0.12 }}
      whileHover={{ y: -8, boxShadow: p.highlight ? "0 0 60px rgba(99,102,241,0.35)" : "0 20px 60px rgba(0,0,0,0.3)" }}
      className={`lp-pricing-card ${p.highlight ? "lp-pricing-featured" : ""}`}>
      {p.highlight && <div className="lp-pricing-badge">Most popular</div>}
      <h3 className="lp-pricing-name">{p.name}</h3>
      <div className="lp-pricing-price">
        {p.price === null ? <span className="lp-price-custom">Custom</span>
          : p.price === 0 ? <span className="lp-price-free">Free</span>
          : <><span className="lp-price-currency">₹</span><span className="lp-price-num">{p.price}</span><span className="lp-price-period">/{p.period}</span></>}
      </div>
      <ul className="lp-pricing-features">
        {p.features.map(f => <li key={f}><Check size={15} />{f}</li>)}
      </ul>
      <motion.button whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
        className={p.highlight ? "lp-btn-primary lp-btn-full" : "lp-btn-outline lp-btn-full"}
        onClick={onGetStarted}>{p.cta}</motion.button>
    </motion.div>
  );
}

function Pricing({ onHirerClick }) {
  return (
    <section id="pricing" className="lp-section">
      <SectionHeading badge="Pricing" title="Simple, transparent pricing" subtitle="Start free. Scale when you're ready." />
      <div className="lp-pricing-grid">
        {PRICING.map((p, i) => <PricingCard key={p.name} p={p} i={i} onGetStarted={onHirerClick} />)}
      </div>
    </section>
  );
}

// ── FAQ ───────────────────────────────────────────────────────────────────────
const FAQS = [
  { q: "How does the AI interview work?", a: "Aria, our AI interviewer, adapts questions based on the candidate's resume and responses in real time — probing technical depth, reasoning, and communication just like a senior engineer would." },
  { q: "Can I customise the interview for my stack?", a: "Yes. HireAI parses your job description and configures relevant questions automatically. You can also add custom questions or topics." },
  { q: "Is the free plan really free?", a: "Yes. The free tier lets you post 1 job and screen unlimited candidates on that role, forever. No credit card required." },
  { q: "How accurate is the scoring?", a: "Our scoring correlates strongly with human assessments. Teams report that candidates ranked in the top quartile by HireAI consistently outperform those who weren't." },
  { q: "Does it work for non-engineering roles?", a: "It's optimised for technical roles today. Support for product, design, and operations roles is coming soon." },
];
function FAQ() {
  const [open, setOpen] = useState(null);
  return (
    <section id="faq" className="lp-section lp-section-alt">
      <SectionHeading badge="FAQ" title="Questions, answered" />
      <div className="lp-faq">
        {FAQS.map((f, i) => (
          <motion.div key={i} className={`lp-faq-item ${open === i ? "open" : ""}`} layout>
            <button className="lp-faq-q" onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}>
              <span>{f.q}</span>
              <motion.span animate={{ rotate: open === i ? 45 : 0 }} transition={{ duration: 0.25 }} className="lp-faq-icon">+</motion.span>
            </button>
            <AnimatePresence initial={false}>
              {open === i && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3, ease: "easeInOut" }}
                  className="lp-faq-a"><p>{f.a}</p></motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ))}
      </div>
    </section>
  );
}

// ── Final CTA ─────────────────────────────────────────────────────────────────
function FinalCTA({ onHirerClick, onCandidateClick }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  return (
    <section className="lp-cta-section">
      <Blobs />
      <motion.div ref={ref} variants={stagger} initial="hidden" animate={inView ? "visible" : "hidden"} className="lp-cta-inner">
        <motion.h2 variants={fadeUp} className="lp-cta-h2">Ready to transform your hiring?</motion.h2>
        <motion.p variants={fadeUp} className="lp-cta-sub">Two portals, one platform — whether you're screening talent or landing your next role.</motion.p>
        <motion.div variants={fadeUp} className="lp-portal-choice">
          <motion.button whileHover={{ scale: 1.06, boxShadow: "0 0 40px rgba(99,102,241,0.5)" }}
            whileTap={{ scale: 0.95 }} className="lp-portal-btn lp-portal-hirer" onClick={onHirerClick}>
            <div className="lp-portal-icon">🏢</div>
            <div>
              <div className="lp-portal-label">Employer portal</div>
              <div className="lp-portal-desc">Post jobs, run AI interviews, hire faster</div>
            </div>
            <ArrowRight size={18} className="lp-portal-arrow" />
          </motion.button>
          <motion.button whileHover={{ scale: 1.06, boxShadow: "0 0 40px rgba(56,189,248,0.3)" }}
            whileTap={{ scale: 0.95 }} className="lp-portal-btn lp-portal-candidate" onClick={onCandidateClick}>
            <div className="lp-portal-icon">🧑‍💻</div>
            <div>
              <div className="lp-portal-label">Candidate portal</div>
              <div className="lp-portal-desc">Find jobs, get interviewed by AI, get scored</div>
            </div>
            <ArrowRight size={18} className="lp-portal-arrow" />
          </motion.button>
        </motion.div>
      </motion.div>
    </section>
  );
}

// ── Footer ────────────────────────────────────────────────────────────────────
function Footer() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  return (
    <motion.footer ref={ref} variants={fadeIn} initial="hidden" animate={inView ? "visible" : "hidden"} className="lp-footer">
      <div className="lp-footer-inner">
        <div className="lp-footer-brand">
          <div className="lp-footer-logo"><div className="lp-logo-dot" /><span className="lp-logo-text">HireAI</span></div>
          <p className="lp-footer-tagline">AI-powered technical hiring for modern engineering teams.</p>
          <div className="lp-footer-socials">
            {[<GitBranch size={18}/>, <Mail size={18}/>, <Globe2 size={18}/>].map((icon, i) => (
              <motion.a key={i} href="#" whileHover={{ scale: 1.2, color: "#818cf8" }} className="lp-social-link">{icon}</motion.a>
            ))}
          </div>
        </div>
        <div className="lp-footer-cols">
          {[
            { title: "Product", links: ["Features", "Pricing", "Changelog", "Roadmap"] },
            { title: "Company", links: ["About", "Blog", "Careers", "Press"] },
            { title: "Legal", links: ["Privacy", "Terms", "Security", "Cookies"] },
          ].map(col => (
            <div key={col.title} className="lp-footer-col">
              <div className="lp-footer-col-title">{col.title}</div>
              {col.links.map(l => <a key={l} href="#" className="lp-footer-link">{l}</a>)}
            </div>
          ))}
        </div>
      </div>
      <div className="lp-footer-bottom">
        <span>© 2026 HireAI. All rights reserved.</span>
        <span>Built with ❤️ for engineering teams</span>
      </div>
    </motion.footer>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function LandingPage({ onHirerClick, onCandidateClick }) {
  return (
    <div className="lp-root">
      <Navbar onHirerClick={onHirerClick} onCandidateClick={onCandidateClick} />
      <Hero onHirerClick={onHirerClick} onCandidateClick={onCandidateClick} />
      <LogoCloud />
      <Features />
      <HowItWorks />
      <Stats />
      <Testimonials />
      <Pricing onHirerClick={onHirerClick} />
      <FAQ />
      <FinalCTA onHirerClick={onHirerClick} onCandidateClick={onCandidateClick} />
      <Footer />
    </div>
  );
}
