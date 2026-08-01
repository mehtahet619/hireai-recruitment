import React from "react";

export default function LandingPage({ onCandidateClick, onRecruiterClick, onPricingClick }) {
  return (
    <div className="landing-page">
      <section className="hero">
        <div className="hero-content">
          <div className="hero-badge">
            <span className="hero-dot"></span>
            AI-Powered Hiring Platform
          </div>
          <h1 className="hero-title">
            Hire Smarter. <br />
            <span className="gradient-text">Interview Faster.</span>
          </h1>
          <p className="hero-subtitle">
            End-to-end AI recruitment that automates resume screening, conducts intelligent interviews,
            and ranks candidates objectively ΓÇö so you focus on people, not paperwork.
          </p>
          <div className="hero-cta">
            <button className="btn-primary" onClick={onCandidateClick}>
              Find Jobs & Apply
              <span className="btn-arrow">ΓåÆ</span>
            </button>
            <button className="btn-primary-alt" onClick={onRecruiterClick}>
              I'm Hiring ΓÇö Start Free
              <span className="btn-arrow">ΓåÆ</span>
            </button>
          </div>
          <div className="hero-stats">
            <div className="stat">
              <div className="stat-number">10x</div>
              <div className="stat-label">Faster Screening</div>
            </div>
            <div className="stat-divider"></div>
            <div className="stat">
              <div className="stat-number">85%</div>
              <div className="stat-label">Time Saved</div>
            </div>
            <div className="stat-divider"></div>
            <div className="stat">
              <div className="stat-number">98%</div>
              <div className="stat-label">Bias Reduction</div>
            </div>
          </div>
        </div>
        <div className="hero-visual">
          <div className="visual-card visual-card-1">
            <div className="visual-card-header">
              <div className="visual-avatar" style={{background: "linear-gradient(135deg, #1f6feb, #8957e5)"}}>AI</div>
              <div>
                <div className="visual-title">AI Interviewer</div>
                <div className="visual-subtitle">Live ΓÇó Speaking</div>
              </div>
              <div className="pulse-dot"></div>
            </div>
            <div className="visual-bubble visual-bubble-left">
              Tell me about a time you led a challenging project.
            </div>
            <div className="visual-bubble visual-bubble-right">
              I spearheaded a migration to microservices that improved latency by 40%...
            </div>
            <div className="typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
          <div className="visual-card visual-card-2">
            <div className="score-ring">
              <svg viewBox="0 0 100 100" className="score-svg">
                <circle cx="50" cy="50" r="42" stroke="#eaeef2" strokeWidth="8" fill="none" />
                <circle cx="50" cy="50" r="42" stroke="url(#scoreGradient)" strokeWidth="8" fill="none"
                        strokeDasharray="264" strokeDashoffset="66" strokeLinecap="round"
                        transform="rotate(-90 50 50)" />
                <defs>
                  <linearGradient id="scoreGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#1f6feb" />
                    <stop offset="100%" stopColor="#2da44e" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="score-center">
                <div className="score-value">75</div>
                <div className="score-label">Fit Score</div>
              </div>
            </div>
            <div className="match-tags">
              <span className="match-tag match-tag-green">Γ£ô React Expert</span>
              <span className="match-tag match-tag-green">Γ£ô 5y+ Exp</span>
              <span className="match-tag match-tag-yellow">~ Node.js</span>
            </div>
          </div>
        </div>
      </section>

      <section className="trusted">
        <div className="trusted-label">Trusted by modern teams</div>
        <div className="trusted-logos">
          <div className="logo-item">Γùå NovaTech</div>
          <div className="logo-item">Γùç CloudScale</div>
          <div className="logo-item">Γûá DataForge</div>
          <div className="logo-item">ΓùÅ DevPilot</div>
          <div className="logo-item">Γû▓ ScaleHub</div>
        </div>
      </section>

      <section className="features">
        <div className="section-header">
          <div className="section-eyebrow">How It Works</div>
          <h2 className="section-title">Everything you need, in one platform</h2>
          <p className="section-subtitle">
            From job posting to offer letter ΓÇö AI handles the busywork, you make the decisions.
          </p>
        </div>
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon feature-icon-blue">≡ƒôï</div>
            <h3 className="feature-title">Smart Job Posting</h3>
            <p className="feature-desc">
              Post jobs in seconds. AI drafts compelling descriptions and optimizes for reach.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon feature-icon-purple">≡ƒöì</div>
            <h3 className="feature-title">Resume Screening</h3>
            <p className="feature-desc">
              Parse hundreds of resumes instantly. AI scores fit against your requirements.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon feature-icon-green">≡ƒÄÖ∩╕Å</div>
            <h3 className="feature-title">AI Interviews</h3>
            <p className="feature-desc">
              Automated 24/7 interviews with voice, video, and screen share capabilities.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon feature-icon-orange">≡ƒôè</div>
            <h3 className="feature-title">Objective Ranking</h3>
            <p className="feature-desc">
              Data-driven candidate scoring with detailed transcripts and feedback.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon feature-icon-pink">≡ƒöÆ</div>
            <h3 className="feature-title">Privacy & Compliance</h3>
            <p className="feature-desc">
              GDPR-ready consent management, data erasure, and audit trails built-in.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon feature-icon-teal">≡ƒöù</div>
            <h3 className="feature-title">HR Integrations</h3>
            <p className="feature-desc">
              Connect with Slack, GitHub, Jira, and your HRIS for seamless workflows.
            </p>
          </div>
        </div>
      </section>

      <section className="split">
        <div className="split-card split-candidate">
          <div className="split-icon">≡ƒÆ╝</div>
          <h2>Looking for your next role?</h2>
          <p>
            Browse open positions, apply in minutes, and complete interviews on your schedule ΓÇö
            day or night.
          </p>
          <ul className="split-list">
            <li>Γ£ô No more phone tag ΓÇö interview 24/7</li>
            <li>Γ£ô Transparent scoring and feedback</li>
            <li>Γ£ô Privacy-first: you control your data</li>
            <li>Γ£ô Practice mode to build confidence</li>
          </ul>
          <button className="btn-primary btn-wide" onClick={onCandidateClick}>
            Browse Jobs & Apply ΓåÆ
          </button>
        </div>
        <div className="split-card split-recruiter">
          <div className="split-icon">≡ƒÄ»</div>
          <h2>Hiring for your team?</h2>
          <p>
            Post jobs, screen hundreds of applicants, and let AI run first-round interviews
            while you focus on culture fit.
          </p>
          <ul className="split-list">
            <li>Γ£ô Post unlimited jobs for free</li>
            <li>Γ£ô AI screens 100% of resumes fairly</li>
            <li>Γ£ô Conduct interviews on autopilot</li>
            <li>Γ£ô Rank candidates objectively</li>
          </ul>
          <button className="btn-primary btn-wide" onClick={onRecruiterClick}>
            Start Hiring Free ΓåÆ
          </button>
        </div>
      </section>

      <section className="pricing-cta-section">
        <div className="pricing-cta-inner">
          <h2>Simple, transparent pricing</h2>
          <p>
            Start free, upgrade when you're ready. No credit card required.
          </p>
          <button className="btn-primary btn-large" onClick={onPricingClick}>
            View Pricing Plans ΓåÆ
          </button>
        </div>
      </section>

      <section className="faq">
        <div className="section-header">
          <div className="section-eyebrow">FAQ</div>
          <h2 className="section-title">Frequently asked questions</h2>
        </div>
        <div className="faq-list">
          <div className="faq-item">
            <h4>How does the AI interview work?</h4>
            <p>Our AI interviewer asks role-specific questions, analyzes responses in real-time, and evaluates candidates on skills, experience, and communication. Supports voice, text, video, and screen sharing.</p>
          </div>
          <div className="faq-item">
            <h4>Is candidate data private?</h4>
            <p>Yes. We're GDPR-compliant with full consent management, data erasure, and audit trails. Candidates control their own data through our privacy portal.</p>
          </div>
          <div className="faq-item">
            <h4>Can I integrate with my existing tools?</h4>
            <p>Absolutely. We offer native integrations with Slack, GitHub, Jira, and popular HRIS systems. Our API makes custom integrations straightforward.</p>
          </div>
          <div className="faq-item">
            <h4>How accurate is the scoring?</h4>
            <p>Our scoring uses multiple evaluation dimensions with calibrated models. You can customize weights and review full transcripts with reasoning for every score.</p>
          </div>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="footer-brand">
          <h3>HireAI</h3>
          <p>AI-powered hiring, human-centered decisions.</p>
        </div>
        <div className="footer-links">
          <div className="footer-col">
            <h5>Product</h5>
            <button className="footer-link" onClick={onCandidateClick}>Find Jobs</button>
            <button className="footer-link" onClick={onRecruiterClick}>For Employers</button>
            <button className="footer-link" onClick={onPricingClick}>Pricing</button>
          </div>
          <div className="footer-col">
            <h5>Company</h5>
            <span className="footer-link muted">About</span>
            <span className="footer-link muted">Contact</span>
            <span className="footer-link muted">Careers</span>
          </div>
          <div className="footer-col">
            <h5>Legal</h5>
            <span className="footer-link muted">Privacy</span>
            <span className="footer-link muted">Terms</span>
            <span className="footer-link muted">Security</span>
          </div>
        </div>
        <div className="footer-bottom">
          <span>┬⌐ 2026 HireAI. All rights reserved.</span>
        </div>
      </footer>
    </div>
  );
}
