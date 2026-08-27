from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from database import get_db
from models.chat import ChatRoom, RoomMember, Message
from models.project import Project
from models.team import Team
from models.user import User
from schemas.chat import ChatRoomCreate
from websocket_manager import manager
import json
from datetime import datetime
import os
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

router = APIRouter(prefix="/chat", tags=["Chat"])

def get_project_member_ids(project_id: int, db: Session) -> list[int]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return []
        
    team_ids = []
    
    # 1. Obter equipas ligadas ao projeto
    if getattr(project, "team_ids", None) and isinstance(project.team_ids, list):
        team_ids.extend(project.team_ids)
    elif getattr(project, "team_id", None):
        team_ids.append(project.team_id)
        
    if getattr(project, "teams", None):
        team_ids.extend([t.id for t in project.teams if hasattr(t, "id")])

    # 2. Obter projetos associados a partir da lista das equipas
    all_teams = db.query(Team).all()
    for t in all_teams:
        proj_ids = getattr(t, "project_ids", []) or []
        if getattr(t, "project_id", None) == project_id or project_id in proj_ids:
            team_ids.append(t.id)

    team_ids = list(set(team_ids))
    member_ids = []
    
    # 3. Adicionar membros e líderes das equipas
    if team_ids:
        matched_teams = db.query(Team).filter(Team.id.in_(team_ids)).all()
        for t in matched_teams:
            if getattr(t, "owner_id", None):
                member_ids.append(t.owner_id)
            if getattr(t, "leader_id", None):
                member_ids.append(t.leader_id)
            if hasattr(t, "members") and t.members:
                for m in t.members:
                    if hasattr(m, "id"):
                        member_ids.append(m.id)
                    elif isinstance(m, int):
                        member_ids.append(m)
            if hasattr(t, "users") and t.users:
                for u in t.users:
                    if hasattr(u, "id"):
                        member_ids.append(u.id)

    # 4. Adicionar Gestor do Projeto
    manager_id = getattr(project, "manager_id", None) or getattr(project, "project_manager_id", None)
    if manager_id:
        member_ids.append(manager_id)

    # 5. Adicionar Administradores e Gestores globais com acesso geral
    admins_managers = db.query(User).filter(
        func.lower(User.role).in_(["admin", "gestor de operações", "manager"])
    ).all()
    for adm in admins_managers:
        member_ids.append(adm.id)

    # 6. Limpar duplicados e validar IDs existentes
    if member_ids:
        valid_users = db.query(User.id).filter(User.id.in_(member_ids)).all()
        return [u[0] for u in valid_users]

    return []

@router.get("/rooms")
def get_user_rooms(
    user_id: int, 
    context: str = Query("direct"), 
    project_id: int = Query(None), 
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    is_admin_or_manager = user and ((user.role or "").lower() in ["admin", "gestor de operações", "manager"])

    query = db.query(ChatRoom)

    if context == "project":
        if project_id:
            query = query.filter(ChatRoom.project_id == project_id)
        else:
            query = query.filter(ChatRoom.project_id.isnot(None))

        if not is_admin_or_manager:
            user_room_ids = db.query(RoomMember.room_id).filter(RoomMember.user_id == user_id).subquery()
            query = query.filter(
                or_(
                    ChatRoom.id.in_(user_room_ids),
                    ChatRoom.is_general == True
                )
            )
    else:
        user_room_ids = db.query(RoomMember.room_id).filter(RoomMember.user_id == user_id).subquery()
        query = query.filter(ChatRoom.project_id.is_(None)).filter(ChatRoom.id.in_(user_room_ids))
        
    rooms = query.all()
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
        elif room.is_general and room.project_id:
            proj = db.query(Project).filter(Project.id == room.project_id).first()
            room_name = f"# Geral - {proj.name}" if proj else "# Geral"
        
        last_msg = db.query(Message).filter(Message.room_id == room.id)\
            .order_by(Message.created_at.desc())\
            .first()
            
        unread = db.query(func.count(Message.id))\
            .filter(Message.room_id == room.id)\
            .filter(Message.sender_id != user_id)\
            .filter(Message.is_read == 0)\
            .scalar()
            
        members_query = db.query(User).join(RoomMember, RoomMember.user_id == User.id)\
            .filter(RoomMember.room_id == room.id).all()
            
        formatted_members = [{"id": m.id, "name": m.name or m.email, "email": m.email} for m in members_query]
            
        result.append({
            "id": room.id,
            "name": room_name,
            "type": room.type,
            "project_id": room.project_id,
            "is_general": room.is_general,
            "parent_id": room.parent_id,
            "members": formatted_members,
            "last_message": last_msg.content if last_msg else "Conversa iniciada",
            "last_time": last_msg.created_at.strftime("%H:%M") if last_msg else "",
            "timestamp": last_msg.created_at if last_msg else datetime.min,
            "unread_count": unread or 0
        })
        
    result.sort(key=lambda x: x["timestamp"], reverse=True)
    return result


@router.post("/projects/{project_id}/sync-general")
def sync_project_general_room(project_id: int, current_user_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
        
    general_room = db.query(ChatRoom).filter(
        ChatRoom.project_id == project_id,
        ChatRoom.is_general == True
    ).first()
    
    if not general_room:
        general_room = ChatRoom(
            name=f"# Geral - {project.name}",
            type="project",
            project_id=project_id,
            is_general=True
        )
        db.add(general_room)
        db.commit()
        db.refresh(general_room)
        
    all_member_ids = get_project_member_ids(project_id, db)
    if current_user_id not in all_member_ids:
        all_member_ids.append(current_user_id)
        
    current_members = db.query(RoomMember.user_id).filter(RoomMember.room_id == general_room.id).all()
    current_member_ids = [m[0] for m in current_members]
    
    for uid in all_member_ids:
        if uid not in current_member_ids:
            db.add(RoomMember(room_id=general_room.id, user_id=uid))
            
    db.commit()
    return {"room_id": general_room.id, "name": general_room.name, "member_count": len(all_member_ids)}

@router.post("/rooms")
def create_room(room_data: ChatRoomCreate, current_user_id: int = Query(...), db: Session = Depends(get_db)):
    if not room_data.name or not room_data.name.strip():
        raise HTTPException(status_code=400, detail="O nome do canal / subchat é obrigatório.")

    member_ids = list(set(room_data.member_ids + [current_user_id]))
    
    if room_data.project_id:
        allowed_project_members = get_project_member_ids(room_data.project_id, db)
        
        for uid in member_ids:
            if uid not in allowed_project_members:
                invalid_user = db.query(User).filter(User.id == uid).first()
                user_label = invalid_user.name or invalid_user.email if invalid_user else f"#{uid}"
                raise HTTPException(
                    status_code=400,
                    detail=f"O utilizador {user_label} não pertence às equipas associadas a este projeto."
                )

    if not room_data.force_create and room_data.project_id:
        existing_rooms = db.query(ChatRoom).filter(ChatRoom.project_id == room_data.project_id).all()
        for r in existing_rooms:
            r_members = [m.user_id for m in db.query(RoomMember).filter(RoomMember.room_id == r.id).all()]
            if set(r_members) == set(member_ids):
                return {
                    "warning": True,
                    "existing_room_id": r.id,
                    "existing_room_name": r.name,
                    "message": f"Já existe um chat ({r.name or 'Geral'}) com exatamente as mesmas pessoas. Desejas criar um novo canal mesmo assim?"
                }

    new_room = ChatRoom(
        name=room_data.name.strip(),
        type=room_data.type or "group",
        project_id=room_data.project_id,
        is_general=room_data.is_general or False,
        parent_id=room_data.parent_id
    )
    db.add(new_room)
    db.commit()
    db.refresh(new_room)

    for uid in member_ids:
        db.add(RoomMember(room_id=new_room.id, user_id=uid))
    db.commit()

    return {"warning": False, "room_id": new_room.id, "name": new_room.name}

@router.post("/rooms/{room_id}/members")
def add_room_member(
    room_id: int, 
    user_id: int = Query(...), 
    current_user_id: int = Query(...), 
    db: Session = Depends(get_db)
):
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Sala não encontrada")

    if room.project_id:
        allowed_members = get_project_member_ids(room.project_id, db)
        if user_id not in allowed_members:
            raise HTTPException(
                status_code=400, 
                detail="Este utilizador não pertence às equipas associadas a este projeto."
            )

    existing = db.query(RoomMember).filter(
        RoomMember.room_id == room_id, 
        RoomMember.user_id == user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="O utilizador já é membro deste canal.")

    db.add(RoomMember(room_id=room_id, user_id=user_id))
    db.commit()

    members = db.query(User).join(RoomMember, RoomMember.user_id == User.id)\
        .filter(RoomMember.room_id == room_id).all()
    return [{"id": m.id, "name": m.name or m.email, "email": m.email} for m in members]

@router.delete("/rooms/{room_id}/members/{user_id}")
def remove_room_member(
    room_id: int, 
    user_id: int, 
    current_user_id: int = Query(...), 
    db: Session = Depends(get_db)
):
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Sala não encontrada")

    if room.is_general:
        raise HTTPException(status_code=400, detail="Não é possível remover membros do canal Geral do projeto.")

    member = db.query(RoomMember).filter(
        RoomMember.room_id == room_id, 
        RoomMember.user_id == user_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Membro não encontrado nesta sala.")

    db.delete(member)
    db.commit()

    members = db.query(User).join(RoomMember, RoomMember.user_id == User.id)\
        .filter(RoomMember.room_id == room_id).all()
    return [{"id": m.id, "name": m.name or m.email, "email": m.email} for m in members]

@router.post("/rooms/direct/{other_user_id}")
def get_or_create_direct_room(other_user_id: int, current_user_id: int, db: Session = Depends(get_db)):
    existing_room = db.query(ChatRoom).join(RoomMember, RoomMember.room_id == ChatRoom.id)\
        .filter(ChatRoom.type == "direct")\
        .filter(ChatRoom.project_id.is_(None))\
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
    user_rooms = db.query(RoomMember.room_id).filter(RoomMember.user_id == user_id).subquery()
    
    unread = db.query(func.count(Message.id))\
        .filter(Message.room_id.in_(user_rooms))\
        .filter(Message.sender_id != user_id)\
        .filter(Message.is_read == 0)\
        .scalar()
        
    return {"unread_count": unread or 0}

@router.put("/rooms/{room_id}/read")
def mark_room_as_read(room_id: int, user_id: int, db: Session = Depends(get_db)):
    db.query(Message).filter(
        Message.room_id == room_id,
        Message.sender_id != user_id,
        Message.is_read == 0
    ).update({"is_read": 1})
    
    db.commit()
    return {"success": True}

@router.post("/summarize")
def summarize_chat(data: dict):
    prompt_text = data.get("prompt")
    if not prompt_text:
        raise HTTPException(status_code=400, detail="Prompt em falta.")
    
    models_to_try = ['gemini-2.5-flash', 'gemini-flash-latest', 'gemini-3.1-pro-preview']
    
    last_error = None
    for m in models_to_try:
        try:
            response = client.models.generate_content(
                model=m,
                contents=prompt_text,
            )
            return {"summary": response.text}
        except Exception as e:
            last_error = str(e)
            continue 
            
    print(f"ERRO CRÍTICO NA IA DO CHAT: {last_error}")
    raise HTTPException(status_code=500, detail="A IA está temporariamente indisponível devido a alta procura. Tenta novamente em segundos.")


@router.delete("/rooms/{room_id}")
def delete_chat_room(
    room_id: int, 
    current_user_id: int = Query(...), 
    db: Session = Depends(get_db)
):
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Canal ou subchat não encontrado.")

    if room.is_general:
        raise HTTPException(status_code=400, detail="Não é permitido apagar o canal Geral do projeto.")

    db.delete(room)
    db.commit()
    return {"success": True, "message": "Subchat apagado com sucesso."}