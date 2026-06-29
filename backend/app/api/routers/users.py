from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import db_session, require_permission
from app.api.schemas import UserCreate, UserOut, UserUpdate
from app.models.rbac import User
from app.repositories.user_repository import UserRepository
from app.shared.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(db_session),
    _: object = Depends(require_permission("users:view")),
):
    return UserRepository(db).list()


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission("users:create")),
):
    repo = UserRepository(db)
    if repo.get_by_username(payload.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    if repo.get_by_email(payload.email):
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role_id=payload.role_id,
        is_active=payload.is_active,
    )
    return repo.add(user)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission("users:update")),
):
    repo = UserRepository(db)
    user = repo.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.email is not None:
        user.email = payload.email
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.password:
        user.hashed_password = hash_password(payload.password)
    if payload.role_id is not None:
        user.role_id = payload.role_id
    if payload.is_active is not None:
        user.is_active = payload.is_active
    return repo.save(user)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(require_permission("users:delete")),
):
    repo = UserRepository(db)
    user = repo.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_superuser:
        raise HTTPException(status_code=400, detail="Cannot delete the superuser")
    repo.delete(user)
    return {"status": "deleted"}
