from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, Float, DateTime, Date
from sqlalchemy.orm import relationship
from database import Base

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    priority = Column(String(50), default="Média")
    status = Column(String(50), default="To Do")
    task_type = Column(String(50), nullable=True, default='Geral')
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    final_description = Column(String, nullable=True)
    attachment_path = Column(String, nullable=True)
    
    estimated_hours = Column(Float, default=0.0)
    tracked_hours = Column(Float, default=0.0)
    due_date = Column(DateTime, nullable=True)
    is_running = Column(Boolean, default=False)
    start_date = Column(Date, nullable=True)

    # Relações essenciais do Ticket:
    project = relationship("Project", back_populates="tickets")
    assignee = relationship("User", foreign_keys=[assigned_to_id])

    
    comments = relationship("Comment", back_populates="ticket", cascade="all, delete-orphan")
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)