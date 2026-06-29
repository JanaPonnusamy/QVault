from sqlalchemy.orm import Session

from app.models.acquisition import Notification
from app.repositories.acquisition_repository import NotificationRepository


def push(db: Session, level: str, title: str, message: str = "", source: str = "") -> Notification:
    return NotificationRepository(db).add(
        Notification(level=level, title=title, message=message, source=source)
    )
