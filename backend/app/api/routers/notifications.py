from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import db_session, get_current_user
from app.api.schemas import NotificationList, NotificationOut
from app.repositories.acquisition_repository import NotificationRepository

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
def list_notifications(
    db: Session = Depends(db_session),
    _: object = Depends(get_current_user),
):
    repo = NotificationRepository(db)
    return NotificationList(items=repo.list(), unread=repo.unread_count())


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(db_session),
    _: object = Depends(get_current_user),
):
    NotificationRepository(db).mark_all_read()
    return {"status": "ok"}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    db: Session = Depends(db_session),
    _: object = Depends(get_current_user),
):
    repo = NotificationRepository(db)
    notification = repo.get(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification
