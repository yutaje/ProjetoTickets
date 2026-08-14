from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from database import Base

class DailyReport(Base):
    __tablename__ = "daily_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime)
    status = Column(String, default="Pendente")
    
    # Textos e IA
    summary = Column(Text, nullable=True)             # Vamos usar para o resumo da IA
    detailed_report = Column(Text, nullable=True)
    pending_work = Column(Text, nullable=True)
    incidents = Column(Text, nullable=True)
    observations = Column(Text, nullable=True)
    
    # Numéricos / Adicionais
    overtime_hours = Column(Float, nullable=True)
    kilometers = Column(Float, nullable=True)
    materials_used = Column(Text, nullable=True)
    
    # A resposta do Manager
    rejection_reason = Column(Text, nullable=True)    # Motivo de recusa
    
    image_path = Column(String, nullable=True)
    submitted_at = Column(DateTime, nullable=True)