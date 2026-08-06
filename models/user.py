from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    role = Column(String(50), default="operator") 
    is_active = Column(Boolean, default=True)


    #relacoes
    tickets_assigned = relationship("Ticket", back_populates="assignee", foreign_keys="Ticket.assigned_to")
    comments = relationship("Comment", back_populates="author")