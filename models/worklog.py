from sqlalchemy import Column, Integer, Float, Date, ForeignKey
from database import Base
from datetime import date

class WorkLog(Base):
    __tablename__ = "worklogs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    ticket_id = Column(Integer, ForeignKey("tickets.id"))
    hours = Column(Float, default=0.0)
    log_date = Column(Date, default=date.today)