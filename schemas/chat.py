from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class MemberSimple(BaseModel):
    id: int
    name: Optional[str] = None
    email: str

    class Config:
        orm_mode = True
        from_attributes = True

class MessageResponse(BaseModel):
    id: int
    room_id: int
    sender_id: int
    sender_name: Optional[str] = None
    content: str
    created_at: datetime
    is_read: int

    class Config:
        orm_mode = True
        from_attributes = True

class ChatRoomCreate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = "direct"  # "direct", "group" ou "project"
    member_ids: List[int]
    project_id: Optional[int] = None
    is_general: Optional[bool] = False
    parent_id: Optional[int] = None
    force_create: Optional[bool] = False  # Se True, cria mesmo que já exista um grupo com os mesmos membros

class ChatRoomResponse(BaseModel):
    id: int
    name: Optional[str] = None
    type: str
    project_id: Optional[int] = None
    is_general: bool = False
    parent_id: Optional[int] = None
    members: List[MemberSimple] = []
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None
    unread_count: int = 0

    class Config:
        orm_mode = True
        from_attributes = True

class MessageCreate(BaseModel):
    content: str