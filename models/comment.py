from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String(1000), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)


    #relacao
    ticket = relationship("Ticket", back_populates="comments")
    author = relationship("User", back_populates="comments")