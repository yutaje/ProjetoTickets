from sqlalchemy import Column, Integer, Float, ForeignKey, Date, DateTime
from sqlalchemy.sql import func
from database import Base # Ajusta o import da tua Base consoante o teu projeto
from sqlalchemy.orm import relationship


class TimeLog(Base):
    __tablename__ = "time_logs"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, index=True, nullable=False) # A data em que o trabalho foi feito
    
    # 1. MODO ANTIGO (Cronómetro): Guarda a quantidade de tempo gasto nesta sessão
    hours_spent = Column(Float, default=0.0)
    
    # 2. NOVO MODO (Horário da Escola): Grava o momento exato do início e do fim
    start_time = Column(DateTime(timezone=True), default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True) # Fica vazio até o user carregar no Stop

    ticket = relationship("Ticket", back_populates="time_logs")