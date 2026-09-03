from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models.notification import Notification
from models.user import User
from core.security import get_current_user
from websocket_manager import manager  # Certifica-te que o gestor de websockets está a este nível

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)

# Schema para receber os dados enviados pelo Frontend (JSON)
class NotificationCreate(BaseModel):
    user_id: int
    title: str
    message: str

@router.get("/")
def get_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).all()

# ONDE MUDAS/ADICIONAS A ROTA POST: É esta aqui em baixo 👇
@router.post("/")
async def create_notification(
    data: NotificationCreate, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    try:
        texto_completo = f"[{data.title}] {data.message}"

        # 1. Guarda sempre na base de dados primeiro[cite: 2]
        nova_notif = Notification(
            user_id=data.user_id,
            message=texto_completo,
            is_read=False
        )
        db.add(nova_notif)
        db.commit()
        db.refresh(nova_notif)

        # 2. Tenta enviar por WebSocket sem rebentar o servidor se o método diferir
        try:
            if hasattr(manager, 'send_personal_message'):
                await manager.send_personal_message(
                    {"id": nova_notif.id, "title": data.title, "message": data.message, "is_read": False},
                    data.user_id
                )
            elif hasattr(manager, 'send_message'):
                await manager.send_message(
                    {"id": nova_notif.id, "title": data.title, "message": data.message, "is_read": False},
                    data.user_id
                )
        except Exception as ws_error:
            print("Aviso WebSocket (ignorado):", ws_error)

        return {"success": True, "data": nova_notif}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) 

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