from sqlalchemy import Column, ForeignKey, Integer, String, Text, Date, Table, Boolean
from sqlalchemy.orm import relationship
from database import Base

# Tabela associativa Muitos-para-Muitos entre Projetos e Equipas
project_teams = Table(
    "project_teams",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("team_id", Integer, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
)

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    description = Column(Text, nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    manager_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    due_date = Column(Date, nullable=True)
    
    # Campo para indicar se o projeto foi arquivado/terminado
    is_archived = Column(Boolean, default=False)

    # Relações
    teams = relationship("Team", secondary=project_teams, backref="projects")
    tickets = relationship("Ticket", back_populates="project", cascade="all, delete-orphan")