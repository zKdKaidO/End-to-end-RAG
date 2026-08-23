import { FormEvent, useState } from "react";
import { Scale } from "lucide-react";
import { api } from "../api/client";
import { ErrorNotice } from "../components/Common";
import type { AuthUser } from "../types";


export function LoginPage({ onAuthenticated }: { onAuthenticated: (user: AuthUser) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      onAuthenticated(await api.login(email, password));
    } catch (value) {
      setError(value);
    } finally {
      setSubmitting(false);
    }
  };

  return <main className="login-page">
    <form className="login-card panel" onSubmit={submit}>
      <div className="login-brand"><span className="brand-mark"><Scale size={20} /></span><div><strong>Legal RAG</strong><small>Secure research workstation</small></div></div>
      <div><span className="eyebrow">Authentication</span><h1>Sign in</h1><p>Use the account provisioned by an administrator.</p></div>
      <ErrorNotice error={error} title="Unable to sign in" />
      <label>Email<input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
      <button className="primary" disabled={submitting}>{submitting ? "Signing in…" : "Sign in"}</button>
    </form>
  </main>;
}
