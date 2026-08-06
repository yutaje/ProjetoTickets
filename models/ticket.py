from sqlalchemy import Column, Float, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="To Do")
    priority = Column(String(50), default="Média")
    deadline = Column(DateTime, nullable=True)
    estimated_hours = Column(Float, default=0.0)
    tracked_hours = Column(Float, default=0.0)
    
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)


    #relacao
    project = relationship("Project", back_populates="tickets")
    assignee = relationship("User", foreign_keys=[assigned_to], back_populates="tickets_assigned")
    comments = relationship("Comment", back_populates="ticket", cascade="all, delete-orphan")