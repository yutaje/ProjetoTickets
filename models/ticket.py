from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, Float, DateTime, Date
from sqlalchemy.orm import relationship
from database import Base

class SubTask(Base):
    __tablename__ = "sub_tasks"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    title = Column(String(255), nullable=False)
    is_completed = Column(Boolean, default=False)
    
    # Atribuição da subtarefa a um utilizador específico
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    ticket = relationship("Ticket", back_populates="sub_tasks")
    assignee = relationship("User", foreign_keys=[assigned_to_id])

    is_approved = Column(Boolean, default=True)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=False) # Obrigatório segundo o caderno de encargos
    priority = Column(String(50), default="Média")
    status = Column(String(50), default="To Do")
    
    # Tipologia (ex: Programação, Redes)
    typology_id = Column(Integer, ForeignKey("typologies.id"), nullable=True)
    
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True) # Atribuição por equipa

    final_description = Column(String, nullable=True)
    attachment_path = Column(String, nullable=True)
    
    estimated_hours = Column(Float, default=0.0)
    tracked_hours = Column(Float, default=0.0)
    due_date = Column(DateTime, nullable=True)
    is_running = Column(Boolean, default=False)
    start_date = Column(Date, nullable=True)

    # Motivo de devolução da tarefa ("divórcio")
    return_reason = Column(String(500), nullable=True)

    # Relações essenciais
    project = relationship("Project", back_populates="tickets")
    assignee = relationship("User", foreign_keys=[assigned_to_id])
    typology = relationship("Typology")

    parent_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    blocked_by_id = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    
    comments = relationship("Comment", back_populates="ticket", cascade="all, delete-orphan")
    time_logs = relationship("TimeLog", back_populates="ticket", cascade="all, delete-orphan")
    sub_tasks = relationship("SubTask", back_populates="ticket", cascade="all, delete-orphan")

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id"))