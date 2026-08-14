from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

class TimeLogCreate(BaseModel):
    ticket_id: int
    date: date
    hours_spent: Optional[float] = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class TimeLogUpdate(BaseModel):
    hours_spent: Optional[float] = None
    end_time: Optional[datetime] = None

class TimeLogResponse(BaseModel):
    id: int
    ticket_id: int
    user_id: int
    date: date
    hours_spent: float
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    class Config:
        from_attributes = True