from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DailyReportCreate(BaseModel):
    # O React pode enviar estes campos no fim do dia
    detailed_report: Optional[str] = None
    pending_work: Optional[str] = None
    incidents: Optional[str] = None
    overtime_hours: Optional[float] = None
    kilometers: Optional[float] = None
    observations: Optional[str] = None
    materials_used: Optional[str] = None
    image_path: Optional[str] = None

class DailyReportResponse(BaseModel):
    id: int
    user_id: int
    date: datetime
    status: str
    
    summary: Optional[str] = None
    detailed_report: Optional[str] = None
    pending_work: Optional[str] = None
    incidents: Optional[str] = None
    overtime_hours: Optional[float] = None
    kilometers: Optional[float] = None
    observations: Optional[str] = None
    materials_used: Optional[str] = None
    rejection_reason: Optional[str] = None
    image_path: Optional[str] = None
    submitted_at: Optional[datetime] = None

    class Config:
        from_attributes = True