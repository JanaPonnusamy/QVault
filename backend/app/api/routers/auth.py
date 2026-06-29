from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_current_user
from app.api.schemas import CurrentUserOut, TokenResponse
from app.models.rbac import User
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(db_session),
):
    token = AuthService(db).login(form.username, form.password)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=CurrentUserOut)
def me(user: User = Depends(get_current_user)):
    data = CurrentUserOut.model_validate(user)
    data.permissions = sorted(user.permission_codes())
    return data
