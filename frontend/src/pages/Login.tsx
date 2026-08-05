import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { apiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useBranding } from "../branding/BrandingContext";

export default function Login() {
  const { user, login } = useAuth();
  const { branding } = useBranding();
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(username, password);
      navigate("/");
    } catch (err) {
      setError(apiError(err, "Login failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="d-flex vh-100 align-items-center justify-content-center"
      style={{ background: "var(--qv-login-bg)" }}
    >
      <div className="card border-0 shadow-lg" style={{ width: 380 }}>
        <div className="card-body p-4 p-md-5">
          <div className="text-center mb-4">
            {branding.logo_url ? (
              <img src={branding.logo_url} alt={branding.logo_text} className="qv-login-logo mb-2" />
            ) : (
              <i className={`bi ${branding.logo_icon} qv-brand-icon`} style={{ fontSize: "2.4rem" }} />
            )}
            <h4 className="mt-2 mb-0 fw-bold">{branding.app_name}</h4>
            <div className="text-muted small">{branding.tagline}</div>
          </div>
          {error && <div className="alert alert-danger py-2">{error}</div>}
          <form onSubmit={submit}>
            <div className="mb-3">
              <label className="form-label small fw-medium">Username</label>
              <input
                className="form-control"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                required
              />
            </div>
            <div className="mb-4">
              <label className="form-label small fw-medium">Password</label>
              <input
                type="password"
                className="form-control"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <button className="btn btn-primary w-100" disabled={busy}>
              {busy ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
