import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api/client";
import { StatusBadge } from "./components/Common";
import { AskPage } from "./pages/AskPage";
import { DebugPage } from "./pages/DebugPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { EvaluationPage } from "./pages/EvaluationPage";

export function App() {
  const [status, setStatus] = useState<{ api: string; provider: string; model_id: string } | null>(null);
  useEffect(() => {
    let active = true;
    const check = () => api.status().then((value) => active && setStatus(value)).catch(() => active && setStatus({ api: "unavailable", provider: "unknown", model_id: "—" }));
    check(); const timer = window.setInterval(check, 30_000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">R</span><div><strong>Legal RAG</strong><small>Debug Cockpit V1</small></div></div>
        <nav aria-label="Primary">
          <NavLink to="/documents">Documents</NavLink>
          <NavLink to="/ask">Ask</NavLink>
          <NavLink to="/debug">Debug</NavLink>
          <NavLink to="/evaluation">Evaluation</NavLink>
        </nav>
        <div className="runtime-status">
          <span className="eyebrow">Runtime</span>
          <div>API <StatusBadge value={status?.api ?? "checking"} /></div>
          <div>LLM <StatusBadge value={status?.provider ?? "checking"} /></div>
          <small>{status?.model_id ?? "Resolving model…"}</small>
        </div>
      </aside>
      <main>
        <Routes>
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/debug" element={<DebugPage />} />
          <Route path="/evaluation" element={<EvaluationPage />} />
          <Route path="*" element={<Navigate to="/debug" replace />} />
        </Routes>
      </main>
    </div>
  );
}
