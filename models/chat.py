from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from datetime import datetime
from database import Base

class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=True)  # Nome do grupo (nulo se for DM 1 para 1)
    type = Column(String(50), default="direct")  # "direct" ou "group"

class RoomMember(Base):
    __tablename__ = "room_members"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"))
    user_id = Column(Integer, ForeignKey("users.id"))

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"))
    sender_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Integer, default=0)