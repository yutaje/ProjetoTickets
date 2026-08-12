from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, Text
from database import Base

class DailyReport(Base):
    __tablename__ = "daily_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, index=True, nullable=False)
    
    status = Column(String(50), default="Rascunho") 
    
    summary = Column(Text, nullable=True)
    detailed_report = Column(Text, nullable=True)
    pending_work = Column(Text, nullable=True)
    incidents = Column(Text, nullable=True)
    
    # Extras
    overtime_hours = Column(Float, default=0.0)
    kilometers = Column(Float, default=0.0)

    rejection_reason = Column(String, nullable=True)