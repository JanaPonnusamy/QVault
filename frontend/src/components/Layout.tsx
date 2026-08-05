import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useBranding } from "../branding/BrandingContext";
import { MODULE_GROUPS, MODULES } from "../modules";
import type { Notification } from "../types";

const LEVEL_ICON: Record<string, string> = {
  success: "bi-check-circle-fill text-success",
  error: "bi-x-circle-fill text-danger",
  warning: "bi-exclamation-triangle-fill text-warning",
  info: "bi-info-circle-fill text-primary",
};

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const { user, logout, can } = useAuth();
  const location = useLocation();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const { branding } = useBranding();

  const loadNotifications = useCallback(async () => {
    try {
      const res = await api.get<{ items: Notification[]; unread: number }>("/api/notifications");
      setNotifications(res.data.items);
      setUnread(res.data.unread);
    } catch {
      /* ignore polling errors */
    }
  }, []);

  useEffect(() => {
    loadNotifications();
    const timer = window.setInterval(loadNotifications, 8000);
    return () => window.clearInterval(timer);
  }, [loadNotifications]);

  async function markAllRead() {
    await api.post("/api/notifications/read-all");
    loadNotifications();
  }

  const visibleModules = useMemo(
    () => MODULES.filter((m) => !m.permission || can(m.permission)),
    [can]
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return visibleModules;
    return visibleModules.filter((m) => m.label.toLowerCase().includes(q));
  }, [search, visibleModules]);

  const current = MODULES.find((m) => m.path === location.pathname);

  return (
    <div className="qv-shell">
      <aside className={`qv-sidebar ${collapsed ? "collapsed" : ""}`}>
        <div className="qv-brand">
          {branding.logo_url ? (
            <img src={branding.logo_url} alt={branding.logo_text} className="qv-brand-logo" />
          ) : (
            <i className={`bi ${branding.logo_icon} qv-brand-icon`} />
          )}
          <span>{branding.logo_text}</span>
        </div>
        <nav className="qv-nav">
          {MODULE_GROUPS.map((group) => {
            const items = filtered.filter((m) => m.group === group);
            if (items.length === 0) return null;
            return (
              <div key={group}>
                <div className="qv-nav-group">{group}</div>
                {items.map((m) =>
                  m.available && m.path ? (
                    <NavLink
                      key={m.key}
                      to={m.path}
                      end={m.path === "/"}
                      className={({ isActive }) => `qv-nav-link ${isActive ? "active" : ""}`}
                      title={m.label}
                    >
                      <i className={`bi ${m.icon}`} />
                      <span>{m.label}</span>
                    </NavLink>
                  ) : (
                    <span key={m.key} className="qv-nav-link disabled" title={`${m.label} (coming soon)`}>
                      <i className={`bi ${m.icon}`} />
                      <span>{m.label}</span>
                    </span>
                  )
                )}
              </div>
            );
          })}
        </nav>
      </aside>

      <div className={`qv-main ${collapsed ? "collapsed" : ""}`}>
        <header className="qv-topbar">
          <button className="btn btn-light btn-sm" onClick={() => setCollapsed((c) => !c)}>
            <i className="bi bi-list" />
          </button>
          <div className="qv-searchbox input-group input-group-sm">
            <span className="input-group-text bg-white border-end-0">
              <i className="bi bi-search" />
            </span>
            <input
              className="form-control border-start-0"
              placeholder="Search modules..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="ms-auto d-flex align-items-center gap-3">
            <div className="dropdown">
              <button
                className="btn btn-light btn-sm position-relative"
                title="Notifications"
                data-bs-toggle="dropdown"
                data-bs-auto-close="outside"
                onClick={loadNotifications}
              >
                <i className="bi bi-bell" />
                {unread > 0 && (
                  <span className="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger">
                    {unread > 99 ? "99+" : unread}
                  </span>
                )}
              </button>
              <div
                className="dropdown-menu dropdown-menu-end shadow"
                style={{ width: 340, maxHeight: 420, overflowY: "auto" }}
              >
                <div className="d-flex justify-content-between align-items-center px-3 py-2 border-bottom">
                  <span className="fw-semibold">Notifications</span>
                  {unread > 0 && (
                    <button className="btn btn-link btn-sm p-0 text-decoration-none" onClick={markAllRead}>
                      Mark all read
                    </button>
                  )}
                </div>
                {notifications.length === 0 && (
                  <div className="px-3 py-4 text-center text-muted small">No notifications</div>
                )}
                {notifications.map((n) => (
                  <div
                    key={n.id}
                    className={`px-3 py-2 border-bottom small ${n.is_read ? "" : "bg-light"}`}
                  >
                    <div className="d-flex gap-2">
                      <i className={`bi ${LEVEL_ICON[n.level] ?? LEVEL_ICON.info}`} />
                      <div className="flex-grow-1">
                        <div className="fw-medium">{n.title}</div>
                        {n.message && <div className="text-muted">{n.message}</div>}
                        <div className="text-muted" style={{ fontSize: "0.72rem" }}>
                          {new Date(n.created_at).toLocaleString()}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="dropdown">
              <button
                className="btn btn-light btn-sm dropdown-toggle d-flex align-items-center gap-2"
                data-bs-toggle="dropdown"
              >
                <i className="bi bi-person-circle" />
                <span>{user?.full_name || user?.username}</span>
              </button>
              <ul className="dropdown-menu dropdown-menu-end">
                <li>
                  <span className="dropdown-item-text small text-muted">
                    {user?.role?.name || (user?.is_superuser ? "Superuser" : "No role")}
                  </span>
                </li>
                <li>
                  <span className="dropdown-item-text small text-muted">
                    {branding.tenant_name}
                  </span>
                </li>
                <li>
                  <hr className="dropdown-divider" />
                </li>
                <li>
                  <button className="dropdown-item" onClick={logout}>
                    <i className="bi bi-box-arrow-right me-2" />
                    Sign out
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </header>

        <nav aria-label="breadcrumb" className="px-4 pt-3">
          <ol className="breadcrumb mb-0">
            <li className="breadcrumb-item">
              <Link to="/" className="text-decoration-none">
                Home
              </Link>
            </li>
            <li className="breadcrumb-item active">{current?.label ?? "Page"}</li>
          </ol>
        </nav>

        <main className="qv-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
