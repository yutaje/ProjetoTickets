from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from database import Base

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    priority = Column(String(50), default="Média")
    status = Column(String(50), default="To Do")
    
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    estimated_hours = Column(Float, default=0.0)
    tracked_hours = Column(Float, default=0.0)
    due_date = Column(DateTime, nullable=True)

    # Relações essenciais do Ticket:
    project = relationship("Project", back_populates="tickets")
    assignee = relationship("User", foreign_keys=[assigned_to_id])
    
    # ADICIONA ESTA LINHA SE FALTAR:
    comments = relationship("Comment", back_populates="ticket", cascade="all, delete-orphan")