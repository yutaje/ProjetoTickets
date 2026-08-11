from sqlalchemy import Column, Integer, Float, ForeignKey, Date
from database import Base # Ajusta o import da tua Base consoante o teu projeto

class TimeLog(Base):
    __tablename__ = "time_logs"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, index=True, nullable=False) # A data em que o trabalho foi feito
    hours_spent = Column(Float, default=0.0)