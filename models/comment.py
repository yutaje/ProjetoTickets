from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from datetime import datetime
from database import Base

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(String(1000), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    author_id = Column(Integer, ForeignKey("users.id"))