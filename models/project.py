from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    description = Column(Text, nullable=True)


    #relacao
    tickets = relationship("Ticket", back_populates="project", cascade="all, delete-orphan")