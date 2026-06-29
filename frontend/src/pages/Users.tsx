import { useCallback, useEffect, useState } from "react";

import { api, apiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Modal from "../components/Modal";
import type { Role, User } from "../types";

interface FormState {
  id: number | null;
  username: string;
  email: string;
  full_name: string;
  password: string;
  role_id: number | "";
  is_active: boolean;
}

const EMPTY: FormState = {
  id: null,
  username: "",
  email: "",
  full_name: "",
  password: "",
  role_id: "",
  is_active: true,
};

export default function Users() {
  const { can } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [form, setForm] = useState<FormState | null>(null);
  const [error, setError] = useState("");

  const canCreate = can("users:create");
  const canUpdate = can("users:update");
  const canDelete = can("users:delete");

  const load = useCallback(async () => {
    try {
      const [u, r] = await Promise.all([
        api.get<User[]>("/api/users"),
        can("roles:view") ? api.get<Role[]>("/api/roles") : Promise.resolve({ data: [] as Role[] }),
      ]);
      setUsers(u.data);
      setRoles(r.data);
    } catch (e) {
      setError(apiError(e));
    }
  }, [can]);

  useEffect(() => {
    load();
  }, [load]);

  function openCreate() {
    setForm({ ...EMPTY });
  }

  function openEdit(u: User) {
    setForm({
      id: u.id,
      username: u.username,
      email: u.email,
      full_name: u.full_name,
      password: "",
      role_id: u.role?.id ?? "",
      is_active: u.is_active,
    });
  }

  async function save() {
    if (!form) return;
    setError("");
    try {
      const payload: Record<string, unknown> = {
        email: form.email,
        full_name: form.full_name,
        role_id: form.role_id === "" ? null : form.role_id,
        is_active: form.is_active,
      };
      if (form.password) payload.password = form.password;
      if (form.id == null) {
        payload.username = form.username;
        await api.post("/api/users", payload);
      } else {
        await api.put(`/api/users/${form.id}`, payload);
      }
      setForm(null);
      await load();
    } catch (e) {
      setError(apiError(e));
    }
  }

  async function remove(u: User) {
    if (!confirm(`Delete user "${u.username}"?`)) return;
    try {
      await api.delete(`/api/users/${u.id}`);
      await load();
    } catch (e) {
      setError(apiError(e));
    }
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h3 className="fw-bold mb-0">
          <i className="bi bi-people me-2" />
          Users
        </h3>
        {canCreate && (
          <button className="btn btn-primary" onClick={openCreate}>
            <i className="bi bi-plus-lg me-1" />
            New User
          </button>
        )}
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card border-0 shadow-sm">
        <div className="table-responsive">
          <table className="table table-hover align-middle mb-0">
            <thead className="table-light">
              <tr>
                <th>Username</th>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th className="text-end">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="fw-medium">
                    {u.username}
                    {u.is_superuser && <span className="badge bg-dark ms-2">super</span>}
                  </td>
                  <td>{u.full_name || "—"}</td>
                  <td>{u.email}</td>
                  <td>{u.role?.name ?? <span className="text-muted">—</span>}</td>
                  <td>
                    {u.is_active ? (
                      <span className="badge bg-success">active</span>
                    ) : (
                      <span className="badge bg-secondary">inactive</span>
                    )}
                  </td>
                  <td className="text-end">
                    {canUpdate && (
                      <button className="btn btn-sm btn-outline-primary me-1" onClick={() => openEdit(u)}>
                        <i className="bi bi-pencil" />
                      </button>
                    )}
                    {canDelete && !u.is_superuser && (
                      <button className="btn btn-sm btn-outline-danger" onClick={() => remove(u)}>
                        <i className="bi bi-trash" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Modal
        title={form?.id == null ? "New User" : "Edit User"}
        open={form != null}
        onClose={() => setForm(null)}
        footer={
          <>
            <button className="btn btn-light" onClick={() => setForm(null)}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={save}>
              Save
            </button>
          </>
        }
      >
        {form && (
          <div className="row g-3">
            <div className="col-md-6">
              <label className="form-label">Username</label>
              <input
                className="form-control"
                value={form.username}
                disabled={form.id != null}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
            </div>
            <div className="col-md-6">
              <label className="form-label">Full name</label>
              <input
                className="form-control"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              />
            </div>
            <div className="col-md-6">
              <label className="form-label">Email</label>
              <input
                className="form-control"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="col-md-6">
              <label className="form-label">
                Password {form.id != null && <span className="text-muted small">(leave blank to keep)</span>}
              </label>
              <input
                type="password"
                className="form-control"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>
            <div className="col-md-6">
              <label className="form-label">Role</label>
              <select
                className="form-select"
                value={form.role_id}
                onChange={(e) =>
                  setForm({ ...form, role_id: e.target.value === "" ? "" : Number(e.target.value) })
                }
              >
                <option value="">No role</option>
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="col-md-6 d-flex align-items-end">
              <div className="form-check form-switch">
                <input
                  className="form-check-input"
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
                <label className="form-check-label">Active</label>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
