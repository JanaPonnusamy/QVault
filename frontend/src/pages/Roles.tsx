import { useCallback, useEffect, useMemo, useState } from "react";

import { api, apiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import Modal from "../components/Modal";
import type { Permission, Role } from "../types";

interface FormState {
  id: number | null;
  name: string;
  description: string;
  permissionIds: Set<number>;
}

export default function Roles() {
  const { can } = useAuth();
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [form, setForm] = useState<FormState | null>(null);
  const [error, setError] = useState("");

  const canCreate = can("roles:create");
  const canUpdate = can("roles:update");
  const canDelete = can("roles:delete");

  const load = useCallback(async () => {
    try {
      const [r, p] = await Promise.all([
        api.get<Role[]>("/api/roles"),
        api.get<Permission[]>("/api/permissions"),
      ]);
      setRoles(r.data);
      setPermissions(p.data);
    } catch (e) {
      setError(apiError(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const grouped = useMemo(() => {
    const map: Record<string, Permission[]> = {};
    for (const p of permissions) {
      (map[p.module] ??= []).push(p);
    }
    return map;
  }, [permissions]);

  function openCreate() {
    setForm({ id: null, name: "", description: "", permissionIds: new Set() });
  }

  function openEdit(role: Role) {
    setForm({
      id: role.id,
      name: role.name,
      description: role.description,
      permissionIds: new Set(role.permissions.map((p) => p.id)),
    });
  }

  function togglePerm(id: number) {
    if (!form) return;
    const next = new Set(form.permissionIds);
    next.has(id) ? next.delete(id) : next.add(id);
    setForm({ ...form, permissionIds: next });
  }

  function toggleModule(module: string, on: boolean) {
    if (!form) return;
    const next = new Set(form.permissionIds);
    for (const p of grouped[module]) {
      on ? next.add(p.id) : next.delete(p.id);
    }
    setForm({ ...form, permissionIds: next });
  }

  async function save() {
    if (!form) return;
    setError("");
    try {
      const payload = {
        name: form.name,
        description: form.description,
        permission_ids: [...form.permissionIds],
      };
      if (form.id == null) {
        await api.post("/api/roles", payload);
      } else {
        await api.put(`/api/roles/${form.id}`, payload);
      }
      setForm(null);
      await load();
    } catch (e) {
      setError(apiError(e));
    }
  }

  async function remove(role: Role) {
    if (!confirm(`Delete role "${role.name}"?`)) return;
    try {
      await api.delete(`/api/roles/${role.id}`);
      await load();
    } catch (e) {
      setError(apiError(e));
    }
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h3 className="fw-bold mb-0">
          <i className="bi bi-shield-lock me-2" />
          Roles &amp; Permissions
        </h3>
        {canCreate && (
          <button className="btn btn-primary" onClick={openCreate}>
            <i className="bi bi-plus-lg me-1" />
            New Role
          </button>
        )}
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <div className="row g-3">
        {roles.map((role) => (
          <div className="col-12 col-md-6 col-xl-4" key={role.id}>
            <div className="card border-0 shadow-sm h-100">
              <div className="card-body">
                <div className="d-flex justify-content-between align-items-start">
                  <div>
                    <h6 className="fw-semibold mb-0">
                      {role.name}
                      {role.is_system && <span className="badge bg-dark ms-2">system</span>}
                    </h6>
                    <div className="small text-muted">{role.description || "—"}</div>
                  </div>
                  <div className="btn-group btn-group-sm">
                    {canUpdate && (
                      <button className="btn btn-outline-primary" onClick={() => openEdit(role)}>
                        <i className="bi bi-pencil" />
                      </button>
                    )}
                    {canDelete && !role.is_system && (
                      <button className="btn btn-outline-danger" onClick={() => remove(role)}>
                        <i className="bi bi-trash" />
                      </button>
                    )}
                  </div>
                </div>
                <div className="mt-3">
                  <span className="badge bg-primary-subtle text-primary">
                    {role.permissions.length} permissions
                  </span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <Modal
        title={form?.id == null ? "New Role" : "Edit Role"}
        open={form != null}
        onClose={() => setForm(null)}
        size="lg"
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
          <div>
            <div className="row g-3 mb-3">
              <div className="col-md-5">
                <label className="form-label">Role name</label>
                <input
                  className="form-control"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>
              <div className="col-md-7">
                <label className="form-label">Description</label>
                <input
                  className="form-control"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </div>
            </div>
            <label className="form-label">Permissions</label>
            <div className="border rounded p-2" style={{ maxHeight: 320, overflowY: "auto" }}>
              {Object.entries(grouped).map(([module, perms]) => {
                const allOn = perms.every((p) => form.permissionIds.has(p.id));
                return (
                  <div key={module} className="mb-3">
                    <div className="d-flex justify-content-between align-items-center mb-1">
                      <span className="fw-semibold text-capitalize">{module.replace(/_/g, " ")}</span>
                      <div className="form-check form-switch">
                        <input
                          className="form-check-input"
                          type="checkbox"
                          checked={allOn}
                          onChange={(e) => toggleModule(module, e.target.checked)}
                        />
                      </div>
                    </div>
                    <div className="d-flex flex-wrap gap-3">
                      {perms.map((p) => (
                        <div className="form-check" key={p.id}>
                          <input
                            className="form-check-input"
                            type="checkbox"
                            id={`perm-${p.id}`}
                            checked={form.permissionIds.has(p.id)}
                            onChange={() => togglePerm(p.id)}
                          />
                          <label className="form-check-label" htmlFor={`perm-${p.id}`}>
                            {p.action}
                          </label>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
