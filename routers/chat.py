from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models.chat import ChatRoom, RoomMember, Message
from models.user import User
from websocket_manager import manager
import json
from datetime import datetime

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.get("/rooms")
def get_user_rooms(user_id: int, db: Session = Depends(get_db)):
    rooms = db.query(ChatRoom).join(RoomMember, RoomMember.room_id == ChatRoom.id)\
        .filter(RoomMember.user_id == user_id)\
        .all()
        
    result = []
    for room in rooms:
        room_name = room.name
        if room.type == "direct":
            other_member = db.query(RoomMember).join(User, User.id == RoomMember.user_id)\
                .filter(RoomMember.room_id == room.id)\
                .filter(RoomMember.user_id != user_id)\
                .first()
            if other_member:
                other_user = db.query(User).filter(User.id == other_member.user_id).first()
                room_name = other_user.name or other_user.email if other_user else "Conversa Direta"
        
        last_msg = db.query(Message).filter(Message.room_id == room.id)\
            .order_by(Message.created_at.desc())\
            .first()
            
        # NOVA PARTE: Conta quantas mensagens não lidas existem APENAS nesta sala
        unread = db.query(func.count(Message.id))\
            .filter(Message.room_id == room.id)\
            .filter(Message.sender_id != user_id)\
            .filter(Message.is_read == 0)\
            .scalar()
            
        result.append({
            "id": room.id,
            "name": room_name,
            "type": room.type,
            "last_message": last_msg.content if last_msg else "Conversa iniciada",
            "last_time": last_msg.created_at.strftime("%H:%M") if last_msg else "",
            "timestamp": last_msg.created_at if last_msg else datetime.min,
            "unread_count": unread or 0  # <--- Enviamos isto para o React!
        })
        
    result.sort(key=lambda x: x["timestamp"], reverse=True)
    return result

@router.post("/rooms/direct/{other_user_id}")
def get_or_create_direct_room(other_user_id: int, current_user_id: int, db: Session = Depends(get_db)):
    existing_room = db.query(ChatRoom).join(RoomMember, RoomMember.room_id == ChatRoom.id)\
        .filter(ChatRoom.type == "direct")\
        .filter(RoomMember.user_id.in_([current_user_id, other_user_id]))\
        .group_by(ChatRoom.id)\
        .having(func.count(ChatRoom.id) == 2)\
        .first()
        
    if existing_room:
        return existing_room

    new_room = ChatRoom(type="direct", name=None)
    db.add(new_room)
    db.commit()
    db.refresh(new_room)

    db.add(RoomMember(room_id=new_room.id, user_id=current_user_id))
    db.add(RoomMember(room_id=new_room.id, user_id=other_user_id))
    db.commit()

    return new_room

@router.get("/history/{room_id}")
def get_chat_history(room_id: int, db: Session = Depends(get_db)):
    messages = db.query(Message).filter(Message.room_id == room_id).order_by(Message.created_at.asc()).all()
    return messages

@router.websocket("/ws/{room_id}/{user_id}")
async def chat_websocket(websocket: WebSocket, room_id: int, user_id: int, db: Session = Depends(get_db)):
    await manager.connect(room_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            packet = json.loads(data)
            content = packet.get("content")
            
            if content:
                db_message = Message(room_id=room_id, sender_id=user_id, content=content)
                db.add(db_message)
                db.commit()
                db.refresh(db_message)
                
                response = {
                    "sender_id": user_id,
                    "content": content,
                    "created_at": db_message.created_at.strftime("%H:%M")
                }
                await manager.broadcast(room_id, response)
    except WebSocketDisconnect:
        manager.disconnect(room_id, websocket)


@router.get("/unread-count")
def get_unread_count(user_id: int, db: Session = Depends(get_db)):
    # 1. Descobrir em que salas o utilizador está
    user_rooms = db.query(RoomMember.room_id).filter(RoomMember.user_id == user_id).subquery()
    
    # 2. Contar quantas mensagens nessas salas NÃO foram enviadas por ele e estão com is_read == 0
    unread = db.query(func.count(Message.id))\
        .filter(Message.room_id.in_(user_rooms))\
        .filter(Message.sender_id != user_id)\
        .filter(Message.is_read == 0)\
        .scalar()
        
    return {"unread_count": unread or 0}

@router.put("/rooms/{room_id}/read")
def mark_room_as_read(room_id: int, user_id: int, db: Session = Depends(get_db)):
    # Marca todas as mensagens não lidas desta sala (que não foram enviadas pelo user) como lidas
    db.query(Message).filter(
        Message.room_id == room_id,
        Message.sender_id != user_id,
        Message.is_read == 0
    ).update({"is_read": 1})
    
    db.commit()
    return {"success": True}