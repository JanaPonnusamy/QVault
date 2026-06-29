import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { MODULES } from "../modules";

export default function Dashboard() {
  const { user, can } = useAuth();
  const modules = MODULES.filter((m) => m.key !== "dashboard" && (!m.permission || can(m.permission)));
  const available = modules.filter((m) => m.available);

  return (
    <div>
      <div className="mb-4">
        <h3 className="fw-bold mb-1">Welcome back, {user?.full_name || user?.username}</h3>
        <p className="text-muted mb-0">
          {available.length} active module{available.length === 1 ? "" : "s"} · {modules.length} total in your workspace
        </p>
      </div>

      <div className="row g-3">
        {modules.map((m) => {
          const card = (
            <div className="qv-module-card">
              <div className="qv-module-icon" style={{ background: m.color }}>
                <i className={`bi ${m.icon}`} />
              </div>
              <div className="fw-semibold">{m.label}</div>
              <div className="small text-muted mt-1">
                {m.available ? (
                  <span className="text-success">
                    <i className="bi bi-check-circle-fill me-1" />
                    Available
                  </span>
                ) : (
                  <span>
                    <i className="bi bi-clock me-1" />
                    Coming soon
                  </span>
                )}
              </div>
            </div>
          );
          return (
            <div className="col-12 col-sm-6 col-lg-4 col-xxl-3" key={m.key}>
              {m.available && m.path ? (
                <Link to={m.path} className="text-decoration-none text-reset">
                  {card}
                </Link>
              ) : (
                <div style={{ opacity: 0.65 }}>{card}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
