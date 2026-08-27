from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Float
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class FeedbackRequest(Base):
    __tablename__ = "feedback_requests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Prazo limite para resposta
    

    feedback_type = Column(String, default="pontual") 
    interval_value = Column(Integer, default=1)       
    interval_unit = Column(String, default="days")        
    cyclic_time = Column(String, nullable=True)


    deadline = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


    # Relações
    creator = relationship("User", foreign_keys=[created_by_id])
    ticket = relationship("Ticket")
    project = relationship("Project")
    responses = relationship("FeedbackResponse", back_populates="request", cascade="all, delete-orphan")


class FeedbackResponse(Base):
    __tablename__ = "feedback_responses"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("feedback_requests.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    rating = Column(Integer, nullable=False) # 1 a 5 estrelas
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    request = relationship("FeedbackRequest", back_populates="responses")
    user = relationship("User", foreign_keys=[user_id])