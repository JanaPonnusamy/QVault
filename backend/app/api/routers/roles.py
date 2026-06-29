from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.api.schemas import PermissionOut, RoleCreate, RoleOut, RoleUpdate
from app.models.rbac import Role
from app.repositories.rbac_repository import PermissionRepository, RoleRepository

router = APIRouter(prefix="/api", tags=["rbac"])


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission("roles:view")),
):
    return PermissionRepository(db).list()


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission("roles:view")),
):
    return RoleRepository(db).list()


@router.post("/roles", response_model=RoleOut)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission("roles:create")),
):
    repo = RoleRepository(db)
    if repo.get_by_name(payload.name):
        raise HTTPException(status_code=400, detail="Role name already exists")
    role = Role(name=payload.name, description=payload.description)
    role.permissions = _resolve_permissions(db, payload.permission_ids)
    return repo.add(role)


@router.put("/roles/{role_id}", response_model=RoleOut)
def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission("roles:update")),
):
    repo = RoleRepository(db)
    role = repo.get(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if payload.name is not None:
        role.name = payload.name
    if payload.description is not None:
        role.description = payload.description
    if payload.permission_ids is not None:
        role.permissions = _resolve_permissions(db, payload.permission_ids)
    return repo.save(role)


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission("roles:delete")),
):
    repo = RoleRepository(db)
    role = repo.get(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=400, detail="System roles cannot be deleted")
    repo.delete(role)
    return {"status": "deleted"}


def _resolve_permissions(db: Session, permission_ids: list[int]):
    repo = PermissionRepository(db)
    result = []
    for pid in permission_ids:
        perm = repo.get(pid)
        if perm:
            result.append(perm)
    return result
