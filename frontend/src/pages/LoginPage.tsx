import { FormEvent, useEffect, useState } from "react";
import { FileText, Lightbulb, Scale, Search, Sparkles } from "lucide-react";

import { api } from "../api/client";
import { ErrorNotice } from "../components/Common";
import type { AuthUser } from "../types";

export function LoginPage({
  onAuthenticated,
}: {
  onAuthenticated: (user: AuthUser) => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  const [videoAvailable, setVideoAvailable] = useState(true);

  /*
    Theme hiện tại.

    Version này đổi trực tiếp:
    <html data-theme="dark">

    hoặc:
    <html data-theme="light">

    Chưa persist localStorage ở bước này.
  */
  const [darkMode, setDarkMode] = useState(
    document.documentElement.dataset.theme === "dark"
  );

  useEffect(() => {
    document.documentElement.dataset.theme = darkMode
      ? "dark"
      : "light";
  }, [darkMode]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();

    setSubmitting(true);
    setError(null);

    try {
      onAuthenticated(
        await api.login(email, password)
      );
    } catch (value) {
      setError(value);
    } finally {
      setSubmitting(false);
    }
  };

  const loginWithGoogle = () => {
    /*
      Hiện tại mới là UI.

      Khi backend Google OAuth được implement,
      có thể đổi thành ví dụ:

      window.location.href = "/api/v1/auth/google";
    */
  };

  return (
    <main className="auth-page">

      {/* =====================================================
          LEFT — AUTHENTICATION
          ===================================================== */}

      <section className="auth-panel">
        <div className="auth-content">

          {/* TOP BAR */}
          <header className="auth-topbar">

            <div className="auth-brand">
              <span className="auth-brand-mark">
                <Scale
                  size={19}
                  strokeWidth={1.8}
                />
              </span>

              <div className="auth-brand-copy">
                <strong>Legal RAG</strong>
                <span>
                  AI-powered legal research
                </span>
              </div>
            </div>

            {/* THEME SWITCH */}
            <button
              type="button"
              className="auth-theme-toggle"
              onClick={() =>
                setDarkMode((current) => !current)
              }
              aria-label={
                darkMode
                  ? "Switch to light mode"
                  : "Switch to dark mode"
              }
              title={
                darkMode
                  ? "Light mode"
                  : "Dark mode"
              }
            >
              <Lightbulb
                size={19}
                strokeWidth={1.8}
              />
            </button>

          </header>

          {/* MAIN LOGIN */}
          <div className="auth-main">

            <div className="auth-heading">
              <h1>
                Welcome back
              </h1>

              <p>
                Sign in to continue your legal research.
              </p>
            </div>

            {/* GOOGLE */}
            <button
              type="button"
              className="google-auth-button"
              onClick={loginWithGoogle}
            >
              <span
                className="google-logo"
                aria-hidden="true"
              >
                G
              </span>

              Continue with Google
            </button>

            {/* DIVIDER */}
            <div
              className="auth-divider"
              aria-hidden="true"
            >
              <span />
              <small>or</small>
              <span />
            </div>

            {/* EMAIL / PASSWORD */}
            <form
              className="auth-form"
              onSubmit={submit}
            >
              <ErrorNotice
                error={error}
                title="Unable to sign in"
              />

              <label className="auth-field">
                <span>
                  Email address
                </span>

                <input
                  type="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(event) =>
                    setEmail(event.target.value)
                  }
                />
              </label>

              <label className="auth-field">
                <span>
                  Password
                </span>

                <input
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) =>
                    setPassword(event.target.value)
                  }
                />
              </label>

              <button
                type="submit"
                className="auth-submit"
                disabled={submitting}
              >
                {submitting
                  ? "Signing in…"
                  : "Sign in"}
              </button>

            </form>

            {/* LEGAL */}
            <p className="auth-legal">
              By continuing, you agree to our{" "}
              <a href="#">
                Terms of Service
              </a>
              {" "}and{" "}
              <a href="#">
                Privacy Policy
              </a>.
            </p>

          </div>

          {/* FOOTER */}
          <footer className="auth-footer">
            Secure research workspace
          </footer>

        </div>
      </section>


      {/* =====================================================
          RIGHT — PRODUCT HERO
          ===================================================== */}

      <section
        className="auth-visual"
        aria-label="Legal RAG product preview"
      >

        {/* VIDEO — khi sau này có MP4 */}
        {videoAvailable && (
          <video
            className="auth-video"
            autoPlay
            muted
            loop
            playsInline
            preload="metadata"
            onError={() =>
              setVideoAvailable(false)
            }
          >
            <source
              src="/login-hero.mp4"
              type="video/mp4"
            />
          </video>
        )}


        {/* ===================================================
            FALLBACK HERO
            Hiện khi login-hero.mp4 chưa tồn tại
            =================================================== */}

        {!videoAvailable && (
          <div className="auth-visual-fallback">

            {/* BACKGROUND LIGHT */}
            <div className="hero-glow hero-glow-one" />
            <div className="hero-glow hero-glow-two" />

            {/* HERO COPY */}
            <div className="hero-copy">

              <span className="hero-eyebrow">
                LEGAL INTELLIGENCE
              </span>

              <h2>
                Research with evidence,
                <br />
                not guesswork.
              </h2>

              <p>
                Search legal documents,
                inspect grounded evidence
                and generate citation-backed answers.
              </p>

            </div>


            {/* PRODUCT MOCKUP */}
            <div className="hero-product">

              <div className="hero-window">

                {/* MOCK BROWSER HEADER */}
                <div className="hero-window-header">

                  <div className="hero-window-dots">
                    <span />
                    <span />
                    <span />
                  </div>

                  <small>
                    Legal RAG
                  </small>

                </div>


                {/* MOCK APP BODY */}
                <div className="hero-window-body">

                  {/* MINI SIDEBAR */}
                  <div className="hero-mini-sidebar">

                    <div className="hero-sidebar-logo">
                      <Scale size={16} />
                    </div>

                    <div className="hero-sidebar-item active">
                      <Sparkles size={15} />
                    </div>

                    <div className="hero-sidebar-item">
                      <FileText size={15} />
                    </div>

                    <div className="hero-sidebar-item">
                      <Search size={15} />
                    </div>

                  </div>


                  {/* CHAT MOCK */}
                  <div className="hero-chat">

                    <span className="hero-chat-label">
                      Ask Legal RAG
                    </span>

                    <h3>
                      What are the requirements
                      for terminating a labor contract?
                    </h3>

                    <div className="hero-answer-line wide" />

                    <div className="hero-answer-line" />

                    <div className="hero-answer-line medium" />

                    <div className="hero-sources">
                      <span>S1</span>
                      <span>S2</span>
                      <span>S3</span>
                    </div>

                  </div>

                </div>

              </div>

            </div>

          </div>
        )}

        <div className="auth-visual-shade" />

      </section>

    </main>
  );
}