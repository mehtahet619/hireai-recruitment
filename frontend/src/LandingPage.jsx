import { useEffect, useRef, useState } from "react";
import { motion, useInView, AnimatePresence } from "framer-motion";
import {
  Zap, Search, FileText, BarChart2, CheckCircle, ArrowRight,
  Menu, X, GitBranch, ChevronRight, Sparkles, TrendingUp,
  Clock, Target, Brain, ListChecks
} from "lucide-react";
import "./landing.css";

// ── Animation helpers ─────────────────────────────────────────────────────────
const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] } }
};
const stagger = { visible: { transition: { staggerChildren: 0.1 } } };

function Reveal({ children, delay = 0, className = "" }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <motion.div ref={ref} variants={fadeUp} initial="hidden"
      animate={inView ? "visible" : "hidden"}
      transition={{ delay }}
      className={className}>
      {children}
    </motion.div>
  );
}

// ── Navbar ────────────────────────────────────────────────────────────────────
function Navbar({ onGetStarted, onLogin }) {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 12);
    window.addEventListener("scroll", fn);
    return () => window.removeEventListener("scroll", fn);
  }, []);
  const links = [
    { label: "Features", href: "#features" },
    { label: "How it works", href: "#how-it-works" },
    { label: "Pricing", href: "#pricing" },
    { label: "GitHub", href: "https://github.com/mehtahet619/hireai-recruitment", external: true },  ];
  return (
    <motion.nav initial={{ y: -56, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className={`lp-nav${scrolled ? " lp-nav--scrolled" : ""}`}>
      <div className="lp-nav__inner">
        <a href="#" className="lp-nav__brand" onClick={e => { e.preventDefault(); window.scrollTo(0, 0); }}>
          <span className="lp-nav__dot" />
          <span className="lp-nav__name">HireAI</span>
        </a>
        <div className="lp-nav__links">
          {links.map(l => (
            <a key={l.label} href={l.href}
              target={l.external ? "_blank" : undefined}
              rel={l.external ? "noopener noreferrer" : undefined}
              className="lp-nav__link">
              {l.label}
            </a>
          ))}
        </div>
        <div className="lp-nav__actions">
          <button className="lp-btn lp-btn--ghost" onClick={onLogin}>Log in</button>
          <button className="lp-btn lp-btn--primary" onClick={onGetStarted}>Get started</button>
        </div>
        <button className="lp-nav__burger" onClick={() => setOpen(!open)} aria-label="Toggle menu">
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.25 }}
            className="lp-nav__mobile">
            {links.map(l => (
              <a key={l.label} href={l.href} className="lp-nav__mobile-link"
                target={l.external ? "_blank" : undefined}
                rel={l.external ? "noopener noreferrer" : undefined}
                onClick={() => setOpen(false)}>
                {l.label}
              </a>
            ))}
            <button className="lp-btn lp-btn--primary lp-btn--full" onClick={() => { setOpen(false); onGetStarted(); }}>
              Get started
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.nav>
  );
}

// ── Dashboard mockup ──────────────────────────────────────────────────────────
const JOBS = [
  { title: "Senior Frontend Engineer", company: "Linear", match: 94, status: "Applied", skills: ["React", "TypeScript", "CSS"] },
  { title: "Full Stack Developer", company: "Vercel", match: 88, status: "Interview", skills: ["Next.js", "Node.js", "Postgres"] },
  { title: "Product Engineer", company: "Notion", match: 81, status: "Reviewing", skills: ["React", "Go", "Design systems"] },
];
const STATUS_COLOR = { Applied: "#3b82f6", Interview: "#22c55e", Reviewing: "#f59e0b" };

function DashboardPreview() {
  return (
    <motion.div className="lp-dashboard" initial={{ opacity: 0, y: 40, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.7, delay: 0.35, ease: [0.22, 1, 0.36, 1] }}>
      <div className="lp-dashboard__bar">
        <span className="lp-dashboard__dot red" />
        <span className="lp-dashboard__dot yellow" />
        <span className="lp-dashboard__dot green" />
        <span className="lp-dashboard__title">HireAI — Job Tracker</span>
      </div>
      <div className="lp-dashboard__body">
        <div className="lp-dashboard__stats">
          {[
            { label: "Jobs matched", val: "48", icon: <Target size={14} /> },
            { label: "Applications", val: "12", icon: <ListChecks size={14} /> },
            { label: "Interviews", val: "3", icon: <TrendingUp size={14} /> },
          ].map(s => (
            <div key={s.label} className="lp-dashboard__stat">
              <span className="lp-dashboard__stat-icon">{s.icon}</span>
              <span className="lp-dashboard__stat-val">{s.val}</span>
              <span className="lp-dashboard__stat-label">{s.label}</span>
            </div>
          ))}
        </div>
        <div className="lp-dashboard__section-label">Recommended for you</div>
        {JOBS.map((j, i) => (
          <motion.div key={j.title} className="lp-dashboard__job"
            initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.5 + i * 0.1 }}>
            <div className="lp-dashboard__job-info">
              <div className="lp-dashboard__job-avatar">{j.company[0]}</div>
              <div>
                <div className="lp-dashboard__job-title">{j.title}</div>
                <div className="lp-dashboard__job-company">{j.company}</div>
                <div className="lp-dashboard__job-skills">
                  {j.skills.map(s => <span key={s} className="lp-skill-chip">{s}</span>)}
                </div>
              </div>
            </div>
            <div className="lp-dashboard__job-right">
              <div className="lp-match-ring" style={{ "--pct": `${j.match}%` }}>
                <span>{j.match}%</span>
              </div>
              <div className="lp-status-badge" style={{ color: STATUS_COLOR[j.status] }}>
                {j.status}
              </div>
            </div>
          </motion.div>
        ))}
        <div className="lp-dashboard__ai-strip">
          <Sparkles size={13} />
          <span>AI is tailoring your resume for <strong>Senior Frontend Engineer at Linear</strong></span>
        </div>
      </div>
    </motion.div>
  );
}

// ── Hero ──────────────────────────────────────────────────────────────────────
function Hero({ onGetStarted, onJobsClick }) {
  return (
    <section className="lp-hero">
      <div className="lp-hero__glow" aria-hidden />
      <div className="lp-hero__grid" aria-hidden />
      <div className="lp-container lp-hero__layout">
        <motion.div className="lp-hero__copy" variants={stagger} initial="hidden" animate="visible">
          <motion.div variants={fadeUp} className="lp-pill">
            <Sparkles size={12} /> AI-powered job search
          </motion.div>
          <motion.h1 variants={fadeUp} className="lp-hero__h1">
            Your AI-powered job search,{" "}
            <span className="lp-gradient-text">automated.</span>
          </motion.h1>
          <motion.p variants={fadeUp} className="lp-hero__sub">
            Find relevant jobs, tailor your applications, and spend less time filling forms and more time preparing for interviews.
          </motion.p>
          <motion.div variants={fadeUp} className="lp-hero__ctas">
            <button className="lp-btn lp-btn--primary lp-btn--lg" onClick={onGetStarted}>
              Start applying <ArrowRight size={16} />
            </button>
            <button className="lp-btn lp-btn--outline lp-btn--lg" onClick={onJobsClick}>
              Browse jobs
            </button>
          </motion.div>
          <motion.p variants={fadeUp} className="lp-hero__note">
            Free for candidates &middot; No account required to browse
          </motion.p>
        </motion.div>
        <div className="lp-hero__preview">
          <DashboardPreview />
        </div>
      </div>
    </section>
  );
}

// ── Metrics ───────────────────────────────────────────────────────────────────
function MetricCounter({ to, suffix = "" }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!inView) return;
    let start = 0;
    const step = to / 50;
    const t = setInterval(() => {
      start += step;
      if (start >= to) { setVal(to); clearInterval(t); }
      else setVal(Math.floor(start));
    }, 20);
    return () => clearInterval(t);
  }, [inView, to]);
  return <span ref={ref}>{val.toLocaleString()}{suffix}</span>;
}

const METRICS = [
  { label: "Jobs indexed", val: 24000, suffix: "+" },
  { label: "Applications optimised", val: 8400, suffix: "+" },
  { label: "Resume tailoring passes", val: 15000, suffix: "+" },
  { label: "Hours saved per applicant", val: 12, suffix: "h" },
];

function Metrics() {
  return (
    <section className="lp-metrics">
      <div className="lp-container">
        <Reveal>
          <p className="lp-metrics__label">Built for developers and ambitious job seekers</p>
        </Reveal>
        <div className="lp-metrics__grid">
          {METRICS.map(m => (
            <Reveal key={m.label} className="lp-metrics__card">
              <div className="lp-metrics__val"><MetricCounter to={m.val} suffix={m.suffix} /></div>
              <div className="lp-metrics__desc">{m.label}</div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Features ──────────────────────────────────────────────────────────────────
const FEATURES = [
  { icon: <Search size={22} />, title: "Smart Job Discovery", desc: "HireAI scans multiple sources and surfaces roles that match your skills, experience, and preferences — not just keyword hits." },
  { icon: <FileText size={22} />, title: "Resume Tailoring", desc: "Adapt your resume to each job description automatically. Keeps your experience truthful while maximising relevance." },
  { icon: <Brain size={22} />, title: "AI Application Assistant", desc: "Generate compelling, personalised cover letters and application answers based on the job and your profile." },
  { icon: <ListChecks size={22} />, title: "Application Tracking", desc: "One dashboard for every application. Track status, interviews, rejections, and offers without spreadsheets." },
  { icon: <Zap size={22} />, title: "Match Scoring", desc: "Every job gets an AI match score so you can prioritise the strongest opportunities and skip poor fits." },
  { icon: <BarChart2 size={22} />, title: "Candidate Analytics", desc: "Understand where you stand. Response rates, skills gaps, interview conversion — data to improve your search." },
];

function FeatureCard({ f, i }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  return (
    <motion.div ref={ref} className="lp-feature-card"
      variants={fadeUp} initial="hidden" animate={inView ? "visible" : "hidden"}
      transition={{ delay: (i % 3) * 0.08 }}
      whileHover={{ y: -4 }}>
      <div className="lp-feature-card__icon">{f.icon}</div>
      <h3 className="lp-feature-card__title">{f.title}</h3>
      <p className="lp-feature-card__desc">{f.desc}</p>
    </motion.div>
  );
}

function Features() {
  return (
    <section id="features" className="lp-section">
      <div className="lp-container">
        <Reveal className="lp-section-head">
          <span className="lp-pill">Features</span>
          <h2 className="lp-section-h2">Everything your job search needs</h2>
          <p className="lp-section-sub">One platform to discover, apply, and track — powered by AI at every step.</p>
        </Reveal>
        <div className="lp-features-grid">
          {FEATURES.map((f, i) => <FeatureCard key={f.title} f={f} i={i} />)}
        </div>
      </div>
    </section>
  );
}

// ── How it works ──────────────────────────────────────────────────────────────
const STEPS = [
  { n: "01", title: "Create your profile", desc: "Upload your resume or paste your experience. HireAI builds a rich candidate profile from it." },
  { n: "02", title: "Discover relevant jobs", desc: "AI matches your profile against thousands of live listings and surfaces the best fits first." },
  { n: "03", title: "Let AI prepare your application", desc: "Tailor your resume, generate a cover letter, and prepare application answers — in seconds." },
  { n: "04", title: "Track your progress", desc: "Monitor every application in one place. Never lose track of where you are in any process." },
];

function StepCard({ s, i }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  return (
    <motion.div ref={ref} className="lp-step"
      variants={fadeUp} initial="hidden" animate={inView ? "visible" : "hidden"}
      transition={{ delay: i * 0.1 }}>
      <div className="lp-step__num">{s.n}</div>
      <div className="lp-step__body">
        <h3 className="lp-step__title">{s.title}</h3>
        <p className="lp-step__desc">{s.desc}</p>
      </div>
    </motion.div>
  );
}

function HowItWorks() {
  return (
    <section id="how-it-works" className="lp-section lp-section--alt">
      <div className="lp-container">
        <Reveal className="lp-section-head">
          <span className="lp-pill">Process</span>
          <h2 className="lp-section-h2">From profile to offer in four steps</h2>
        </Reveal>
        <div className="lp-steps">
          {STEPS.map((s, i) => <StepCard key={s.n} s={s} i={i} />)}
        </div>
      </div>
    </section>
  );
}

// ── AI section ────────────────────────────────────────────────────────────────
function AISection() {
  return (
    <section className="lp-ai-section">
      <div className="lp-container">
        <Reveal className="lp-section-head lp-section-head--light">
          <span className="lp-pill lp-pill--dark">AI engine</span>
          <h2 className="lp-section-h2 lp-section-h2--light">AI that understands the job,<br />not just the keywords.</h2>
          <p className="lp-section-sub lp-section-sub--light">Semantic analysis, not regex matching. HireAI reads job descriptions the way a recruiter does.</p>
        </Reveal>
        <div className="lp-ai-flow">
          {["Job description", "AI analysis", "Tailored resume", "Application ready"].map((label, i) => (
            <Reveal key={label} delay={i * 0.1} className="lp-ai-flow__step">
              <div className="lp-ai-flow__box">{label}</div>
              {i < 3 && <ChevronRight className="lp-ai-flow__arrow" size={18} aria-hidden />}
            </Reveal>
          ))}
        </div>
        <Reveal delay={0.4}>
          <div className="lp-ai-card">
            <div className="lp-ai-card__label"><Brain size={14} /> AI analysis example</div>
            <div className="lp-ai-card__row">
              <div className="lp-ai-card__col">
                <div className="lp-ai-card__col-head">Job requires</div>
                {["5y React experience", "TypeScript proficiency", "Design system knowledge", "Cross-functional collab"].map(r => (
                  <div key={r} className="lp-ai-card__item lp-ai-card__item--req">{r}</div>
                ))}
              </div>
              <div className="lp-ai-card__divider" aria-hidden />
              <div className="lp-ai-card__col">
                <div className="lp-ai-card__col-head">Your profile matches</div>
                {["6y React, Next.js", "TypeScript &mdash; daily use", "Led Figma → code system", "3 cross-team projects"].map(m => (
                  <div key={m} className="lp-ai-card__item lp-ai-card__item--match" dangerouslySetInnerHTML={{ __html: `<span class='lp-check'><svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3'><polyline points='20 6 9 17 4 12'/></svg></span> ${m}` }} />
                ))}
              </div>
            </div>
            <div className="lp-ai-card__score">Match score <strong>92%</strong></div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

// ── Open source ───────────────────────────────────────────────────────────────
function OpenSource() {
  return (
    <section className="lp-section lp-section--alt">
      <div className="lp-container">
        <Reveal className="lp-oss">
          <GitBranch size={36} className="lp-oss__icon" />
          <h2 className="lp-section-h2">Built in the open.</h2>
          <p className="lp-section-sub">HireAI is open source. Inspect the code, contribute features, report bugs, and build on the platform.</p>
          <a href="https://github.com/mehtahet619/hireai-recruitment" target="_blank" rel="noopener noreferrer"
            className="lp-btn lp-btn--outline lp-btn--lg">
            <GitBranch size={18} /> View on GitHub
          </a>
        </Reveal>
      </div>
    </section>
  );
}

// ── Final CTA ─────────────────────────────────────────────────────────────────
function FinalCTA({ onGetStarted }) {
  return (
    <section className="lp-cta-section">
      <div className="lp-cta-section__glow" aria-hidden />
      <div className="lp-container">
        <Reveal className="lp-cta">
          <h2 className="lp-cta__h2">Stop searching endlessly.<br />Start applying smarter.</h2>
          <p className="lp-cta__sub">Let HireAI handle the repetitive parts of your job search so you can focus on getting hired.</p>
          <button className="lp-btn lp-btn--primary lp-btn--lg" onClick={onGetStarted}>
            Get started <ArrowRight size={16} />
          </button>
        </Reveal>
      </div>
    </section>
  );
}

// ── Footer ────────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer className="lp-footer">
      <div className="lp-container lp-footer__inner">
        <div className="lp-footer__brand">
          <div className="lp-nav__brand">
            <span className="lp-nav__dot" />
            <span className="lp-nav__name">HireAI</span>
          </div>
          <p className="lp-footer__tagline">AI-powered job search for the modern candidate.</p>
        </div>
        <div className="lp-footer__cols">
          {[
            { head: "Product", links: [{ label: "Features", href: "#features" }, { label: "Pricing", href: "#pricing" }, { label: "How it works", href: "#how-it-works" }] },
            { head: "Company", links: [{ label: "GitHub", href: "https://github.com/mehtahet619/hireai-recruitment", external: true }, { label: "Privacy", href: "#" }, { label: "Terms", href: "#" }] },
          ].map(col => (
            <div key={col.head} className="lp-footer__col">
              <div className="lp-footer__col-head">{col.head}</div>
              {col.links.map(l => (
                <a key={l.label} href={l.href} className="lp-footer__link"
                  target={l.external ? "_blank" : undefined}
                  rel={l.external ? "noopener noreferrer" : undefined}>
                  {l.label}
                </a>
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="lp-container lp-footer__bottom">
        <span>&copy; {new Date().getFullYear()} HireAI. All rights reserved.</span>
        <span>Open source &middot; MIT licence</span>
      </div>
    </footer>
  );
}

// ── Root export ───────────────────────────────────────────────────────────────
export default function LandingPage({ onHirerClick, onCandidateClick }) {
  return (
    <div className="lp-root">
      <Navbar onGetStarted={onHirerClick} onLogin={onHirerClick} />
      <Hero onGetStarted={onHirerClick} onJobsClick={onCandidateClick} />
      <Metrics />
      <Features />
      <HowItWorks />
      <AISection />
      <OpenSource />
      <FinalCTA onGetStarted={onHirerClick} />
      <Footer />
    </div>
  );
}
