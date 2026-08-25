from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=True)  # Nome do grupo ou subchat (nulo se for DM 1 para 1)
    type = Column(String(50), default="direct")  # "direct", "group" ou "project"
    
    # Suporte para Projetos e Subchats
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    is_general = Column(Boolean, default=False)  # True se for o chat geral/automático do projeto
    parent_id = Column(Integer, ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=True)  # ID do canal geral se for um subchat

    # Relacionamentos
    members = relationship("RoomMember", back_populates="room", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="room", cascade="all, delete-orphan")
    sub_rooms = relationship("ChatRoom", backref="parent_room", remote_side=[id])

class RoomMember(Base):
    __tablename__ = "room_members"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    room = relationship("ChatRoom", back_populates="members")
    user = relationship("User")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id", ondelete="CASCADE"))
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Integer, default=0)

    room = relationship("ChatRoom", back_populates="messages")
    sender = relationship("User")