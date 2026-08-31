import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authFetch, setTokens } from "../api";

const AUTH = import.meta.env.VITE_AUTH_URL || "/auth-api";

export default function LoginPage() {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await authFetch(`/v1/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setTokens(data.access_token, data.refresh_token);
      nav("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <h1>Membrane</h1>
        <p className="muted">Agent memory console — sign in via OpenDesk Auth.</p>
        <div className="oauth-row">
          <a className="btn secondary" href={`${AUTH}/v1/oauth/google/start`}>
            Google
          </a>
          <a className="btn secondary" href={`${AUTH}/v1/oauth/github/start`}>
            GitHub
          </a>
        </div>
        <div className="divider">or email</div>
        <form onSubmit={onSubmit}>
          <div className="field">
            <label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
          </div>
          <div className="field">
            <label>Password</label>
            <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required minLength={8} />
          </div>
          <div className="row">
            <button type="submit" disabled={busy}>
              {mode === "login" ? "Sign in" : "Create account"}
            </button>
            <button type="button" className="secondary" onClick={() => setMode(mode === "login" ? "register" : "login")}>
              {mode === "login" ? "Need an account?" : "Have an account?"}
            </button>
          </div>
          {error && <p className="error">{error}</p>}
        </form>
        <p className="muted" style={{ marginTop: "1.25rem", fontSize: "0.85rem" }}>
          OpenDesk Auth is a shared microservice. <Link to="/">Membrane</Link> validates JWTs via JWKS.
        </p>
      </div>
    </div>
  );
}
