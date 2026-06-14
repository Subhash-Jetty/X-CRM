"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import "./hero.css";

const TYPED_WORDS = [
  "high-value customers",
  "WhatsApp campaigns",
  "at-risk segments",
  "personalized messages",
  "campaign analytics",
];

export default function LandingPage() {
  const [wordIndex, setWordIndex] = useState(0);
  const [displayed, setDisplayed] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const word = TYPED_WORDS[wordIndex];
    let timeout: NodeJS.Timeout;

    if (!deleting) {
      if (displayed.length < word.length) {
        timeout = setTimeout(
          () => setDisplayed(word.slice(0, displayed.length + 1)),
          60
        );
      } else {
        timeout = setTimeout(() => setDeleting(true), 2000);
      }
    } else {
      if (displayed.length > 0) {
        timeout = setTimeout(
          () => setDisplayed(displayed.slice(0, -1)),
          30
        );
      } else {
        timeout = setTimeout(() => {
          setDeleting(false);
          setWordIndex((i) => (i + 1) % TYPED_WORDS.length);
        }, 30);
      }
    }

    return () => clearTimeout(timeout);
  }, [displayed, deleting, wordIndex]);

  return (
    <div className="hero-page">
      {/* Floating Nav */}
      <nav className="hero-nav">
        <div className="hero-nav-inner">
          <Link href="/" className="hero-logo">
            <div className="hero-logo-mark">X</div>
            <span className="hero-logo-text">XENO</span>
          </Link>
          <div className="hero-nav-links">
            <Link href="/login" className="btn btn-ghost">
              Sign In
            </Link>
            <Link href="/register" className="btn btn-primary">
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-badge">
          <span className="hero-badge-dot" />
          AI-Native CRM Platform
        </div>

        <h1 className="hero-title">
          Customer engagement,
          <br />
          <span className="text-gradient">powered by intelligence.</span>
        </h1>

        <p className="hero-subtitle">
          Ask your AI assistant to find{" "}
          <span className="typed-text">
            {displayed}
            <span className="typed-cursor">|</span>
          </span>
        </p>

        <div className="hero-ctas">
          <Link href="/register" className="btn btn-primary btn-lg hero-cta-primary">
            Start for Free
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </Link>
          <Link href="/login" className="btn btn-secondary btn-lg">
            Sign In
          </Link>
        </div>

        {/* Feature Cards */}
        <div className="hero-features">
          <div className="feature-card glass-panel">
            <div className="feature-icon" style={{ background: "var(--primary-glow)" }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--primary-light)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </div>
            <h3 className="feature-title">Smart Segments</h3>
            <p className="feature-desc">
              Describe your audience in plain English. Our AI builds the segment
              for you automatically.
            </p>
          </div>

          <div className="feature-card glass-panel">
            <div className="feature-icon" style={{ background: "var(--secondary-glow)" }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--secondary-light)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <h3 className="feature-title">Omnichannel Campaigns</h3>
            <p className="feature-desc">
              Reach customers on WhatsApp, SMS, Email, and RCS — all from a
              single conversation.
            </p>
          </div>

          <div className="feature-card glass-panel">
            <div className="feature-icon" style={{ background: "var(--accent-glow)" }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
              </svg>
            </div>
            <h3 className="feature-title">AI-First Experience</h3>
            <p className="feature-desc">
              Chat with an AI agent that queries data, drafts messages, and
              launches campaigns autonomously.
            </p>
          </div>
        </div>

        {/* Stats */}
        <div className="hero-stats">
          <div className="hero-stat">
            <span className="hero-stat-number">1,000+</span>
            <span className="hero-stat-label">Customers Managed</span>
          </div>
          <div className="hero-stat-divider" />
          <div className="hero-stat">
            <span className="hero-stat-number">5,000+</span>
            <span className="hero-stat-label">Orders Tracked</span>
          </div>
          <div className="hero-stat-divider" />
          <div className="hero-stat">
            <span className="hero-stat-number">4</span>
            <span className="hero-stat-label">Channels Supported</span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="hero-footer">
        <p>
          Built for Xeno FDE Assignment &middot; Powered by Groq &amp; Gemini
        </p>
      </footer>
    </div>
  );
}
