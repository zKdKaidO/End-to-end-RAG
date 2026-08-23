import { useEffect, useState } from "react";
import { Activity, FileText, FlaskConical, LogOut, Moon, Search, Sun } from "lucide-react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api/client";
import { StatusBadge } from "./components/Common";
import { AskPage } from "./pages/AskPage";
import { DebugPage } from "./pages/DebugPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { EvaluationPage } from "./pages/EvaluationPage";
import { LoginPage } from "./pages/LoginPage";
import type { AuthUser } from "./types";

type Theme = "light" | "dark";

const NAVIGATION = [
  { to: "/ask", label: "Ask", icon: Search, admin: false },
  { to: "/documents", label: "Documents", icon: FileText, admin: false },
  { to: "/debug", label: "Debug", icon: Activity, admin: true },
  { to: "/evaluation", label: "Evaluation", icon: FlaskConical, admin: true },
];

function initialTheme(): Theme {
  const stored = window.localStorage.getItem("legal-rag-theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [status, setStatus] = useState({ api: "checking", provider: "checking", model_id: "Resolving model…" });
  const [internalTools, setInternalTools] = useState(false);
  const [theme, setTheme] = useState<Theme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("legal-rag-theme", theme);
  }, [theme]);

  useEffect(() => {
    let active = true;
    api.me().then((value) => { if (active) setUser(value); }).catch(() => { if (active) setUser(null); }).finally(() => { if (active) setAuthLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const unauthorized = () => setUser(null);
    window.addEventListener("legal-rag:unauthorized", unauthorized);
    return () => window.removeEventListener("legal-rag:unauthorized", unauthorized);
  }, []);

  useEffect(() => {
    if (!user) return;
    let active = true;
    const check = async () => {
      const health = await api.health().catch(() => ({ status: "unavailable", service: "api" }));
      if (!active) return;
      if (user.role !== "ADMIN") {
        setInternalTools(false);
        setStatus({ api: health.status === "ok" ? "available" : "unavailable", provider: "restricted", model_id: "Production Legal RAG" });
        return;
      }
      try {
        const value = await api.status();
        if (active) { setInternalTools(true); setStatus(value); }
      } catch {
        if (active) { setInternalTools(false); setStatus({ api: health.status === "ok" ? "available" : "unavailable", provider: "unknown", model_id: "Internal diagnostics disabled" }); }
      }
    };
    void check();
    const timer = window.setInterval(check, 30_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [user]);

  if (authLoading) return <main className="auth-loading" aria-live="polite">Loading secure workspace…</main>;
  if (!user) return <Routes><Route path="*" element={<LoginPage onAuthenticated={setUser} />} /></Routes>;

  const logout = async () => {
    try { await api.logout(); } finally { setUser(null); }
  };

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark" aria-hidden="true">§</span><div className="brand-copy"><strong>Legal RAG</strong><small>Research workstation</small></div></div>
      <nav aria-label="Primary navigation">
        {NAVIGATION.filter((item) => !item.admin || (user.role === "ADMIN" && internalTools)).map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} title={label}><Icon size={17} aria-hidden="true" /><span>{label}</span></NavLink>)}
      </nav>
      <div className="sidebar-footer">
        <div className="signed-in-user"><strong>{user.email}</strong><small>{user.role}</small></div>
        <button className="theme-toggle" onClick={() => void logout()}><LogOut size={16} /><span>Sign out</span></button>
        <button className="theme-toggle" aria-label={theme === "light" ? "Use dark theme" : "Use light theme"} onClick={() => setTheme((value) => value === "light" ? "dark" : "light")}>
          {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}<span>{theme === "light" ? "Dark theme" : "Light theme"}</span>
        </button>
        <div className="runtime-status"><div><span>API</span><StatusBadge value={status.api} /></div><div><span>LLM</span><StatusBadge value={status.provider} /></div><small title={status.model_id}>{status.model_id}</small></div>
      </div>
    </aside>
    <main><Routes>
      <Route path="/documents" element={<DocumentsPage user={user} />} />
      <Route path="/ask" element={<AskPage />} />
      {user.role === "ADMIN" && internalTools ? <Route path="/debug" element={<DebugPage />} /> : null}
      {user.role === "ADMIN" && internalTools ? <Route path="/evaluation" element={<EvaluationPage />} /> : null}
      <Route path="*" element={<Navigate to="/ask" replace />} />
    </Routes></main>
  </div>;
}
