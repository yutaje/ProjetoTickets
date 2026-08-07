from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.notification import Notification
from models.user import User
from core.security import get_current_user

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)

@router.get("/")
def get_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).all()

@router.put("/{notif_id}/read")
def mark_as_read(notif_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    notif = db.query(Notification).filter(Notification.id == notif_id, Notification.user_id == current_user.id).first()
    if notif:
        notif.is_read = True
        db.commit()
    return {"success": True}

@router.put("/read-all")
def mark_all_as_read(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db.query(Notification).filter(Notification.user_id == current_user.id, Notification.is_read == False).update({"is_read": True})
    db.commit()
    return {"success": True}