from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rbac import Permission, Role


class RoleRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, role_id: int) -> Role | None:
        return self.db.get(Role, role_id)

    def get_by_name(self, name: str) -> Role | None:
        return self.db.scalar(select(Role).where(Role.name == name))

    def list(self) -> list[Role]:
        return list(self.db.scalars(select(Role).order_by(Role.id)))

    def add(self, role: Role) -> Role:
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)
        return role

    def save(self, role: Role) -> Role:
        self.db.commit()
        self.db.refresh(role)
        return role

    def delete(self, role: Role) -> None:
        self.db.delete(role)
        self.db.commit()


class PermissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, permission_id: int) -> Permission | None:
        return self.db.get(Permission, permission_id)

    def get_by_code(self, code: str) -> Permission | None:
        return self.db.scalar(select(Permission).where(Permission.code == code))

    def list(self) -> list[Permission]:
        return list(self.db.scalars(select(Permission).order_by(Permission.module, Permission.action)))

    def add(self, permission: Permission) -> Permission:
        self.db.add(permission)
        self.db.commit()
        self.db.refresh(permission)
        return permission
