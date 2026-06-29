from sqlalchemy.orm import Session

from app.models.rbac import User
from app.repositories.user_repository import UserRepository
from app.shared.security import create_access_token, verify_password


class AuthService:
    def __init__(self, db: Session):
        self.users = UserRepository(db)

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.users.get_by_username(username) or self.users.get_by_email(username)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def login(self, username: str, password: str) -> str | None:
        user = self.authenticate(username, password)
        if not user:
            return None
        return create_access_token(user.id)
